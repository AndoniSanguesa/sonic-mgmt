
import logging

import constants

from tests.common.utilities import wait
from tests.common.errors import RunAnsibleModuleFail
from tests.common.platform.device_utils import fanout_switch_port_lookup
from tests.common.config_reload import config_force_option_supported

logger = logging.getLogger(__name__)


def reboot_dut(dut, localhost, cmd, wait_time):
    logger.info("Reboot dut using cmd='%s'" % cmd)
    reboot_task, reboot_res = dut.command(cmd, module_async=True)

    logger.info("Wait for DUT to go down")
    try:
        localhost.wait_for(host=dut.mgmt_ip, port=22, state="stopped", delay=10, timeout=300)
    except RunAnsibleModuleFail as e:
        logger.error("DUT did not go down, exception: " + repr(e))
        if reboot_task.is_alive():
            logger.error("Rebooting is not completed")
            reboot_task.terminate()
        logger.error("reboot result %s" % str(reboot_res.get()))
        assert False, "Failed to reboot the DUT"

    localhost.wait_for(host=dut.mgmt_ip, port=22, state="started", delay=10, timeout=300)
    wait(wait_time, msg="Wait {} seconds for system to be stable.".format(wait_time))


def __recover_interfaces(dut, fanouthosts, result, wait_time):
    action = None
    for port in result['down_ports']:
        logging.warning("Restoring port: {}".format(port))

        pn = str(port).lower()
        if 'portchannel' in pn or 'vlan' in pn:
            action = 'config_reload'
            continue

        fanout, fanout_port = fanout_switch_port_lookup(fanouthosts, dut.hostname, port)
        if fanout and fanout_port:
            fanout.no_shutdown(fanout_port)
        dut.no_shutdown(port)
    wait(wait_time, msg="Wait {} seconds for interface(s) to restore.".format(wait_time))
    return action


def __recover_services(dut, result):
    status   = result['services_status']
    services = [ x for x in status if not status[x] ]
    logging.warning("Service(s) down: {}".format(services))
    return 'reboot' if 'database' in services else 'config_reload'


def __recover_with_command(dut, cmd, wait_time):
    dut.command(cmd)
    wait(wait_time, msg="Wait {} seconds for system to be stable.".format(wait_time))


def adaptive_recover(dut, localhost, fanouthosts, check_results, wait_time):
    outstanding_action = None
    for result in check_results:
        if result['failed']:
            if result['check_item'] == 'interfaces':
                action = __recover_interfaces(dut, fanouthosts, result, wait_time)
            elif result['check_item'] == 'services':
                action = __recover_services(dut, result)
            elif result['check_item'] in [ 'processes', 'bgp' ]:
                action = 'config_reload'
            else:
                action = 'reboot'

            # Any action can override no action or 'config_reload'.
            # 'reboot' is last resort and cannot be overridden.
            if action and (not outstanding_action or outstanding_action == 'config_reload'):
                outstanding_action = action

            logging.warning("Restoring {} with proposed action: {}, final action: {}".format(result, action, outstanding_action))

    if outstanding_action:
        if outstanding_action == "config_reload" and config_force_option_supported(dut):
            outstanding_action = "config_reload_f"
        method    = constants.RECOVER_METHODS[outstanding_action]
        wait_time = method['recover_wait']
        if method["reboot"]:
            reboot_dut(dut, localhost, method["cmd"], wait_time)
        else:
            __recover_with_command(dut, method['cmd'], wait_time)


def recover(dut, localhost, fanouthosts, check_results, recover_method):
    logger.warning("Try to recover %s using method %s" % (dut.hostname, recover_method))
    if recover_method == "config_reload" and config_force_option_supported(dut):
        recover_method = "config_reload_f"
    method    = constants.RECOVER_METHODS[recover_method]
    wait_time = method['recover_wait']
    if method["adaptive"]:
        adaptive_recover(dut, localhost, fanouthosts, check_results, wait_time)
    elif method["reboot"]:
        reboot_dut(dut, localhost, method["cmd"], wait_time)
    else:
        __recover_with_command(dut, method['cmd'], wait_time)


def neighbor_vm_restore(duthost, nbrhosts, tbinfo):
    logger.info("Restoring neighbor VMs for {}".format(duthost))
    mg_facts = duthost.get_extended_minigraph_facts(tbinfo)
    vm_neighbors = mg_facts['minigraph_neighbors']
    lag_facts = duthost.lag_facts(host = duthost.hostname)['ansible_facts']['lag_facts']

    for lag_name in lag_facts['names']:
        nbr_intf = lag_facts['lags'][lag_name]['po_config']['ports'].keys()[0]
        peer_device   = vm_neighbors[nbr_intf]['name']
        nbr_host = nbrhosts[peer_device]['host']
        intf_list = nbrhosts[peer_device]['conf']['interfaces'].keys()
        # restore interfaces and portchannels
        for intf in intf_list:
            nbr_host.no_shutdown(intf)
        asn = nbrhosts[peer_device]['conf']['bgp']['asn']
        # restore BGP session
        nbr_host.no_shutdown_bgp(asn)
