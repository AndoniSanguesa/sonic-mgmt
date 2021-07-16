import pytest
import logging
from tests.common.helpers.assertions import pytest_assert

pytestmark = [
    pytest.mark.disable_loganalyzer,
    pytest.mark.topology("any"),
    pytest.mark.device_type("vs"),
]

def get_interface_status(duthost, interface_name):
    """Returns the administrative status of an interface on the DUT"""

    # Gets information on all interfaces
    output_lines = duthost.command("show interfaces status")["stdout_lines"]

    # Looks for the interface in the collected data
    interface_line = ""

    for line in output_lines:
        data = line.split()
        if data[0] == interface_name:
            interface_line = line
    
    # If the interface is not configured, the test should fail
    pytest_assert(interface_line, "Status for interface {} could not be found. Are you sure its configured?".format(interface_name))

    # Return admin status
    return True if interface_line.split()[8] == "up" else False

def check_vlan_state(duthost):
    """Checks whether the VLAN interface is up or down on the DUT"""
    
    # Gets information on interfaces
    output_lines = duthost.command("show ip interfaces")["stdout_lines"]

    # Checks output for the vlan info
    vlan_line = ""

    for line in output_lines:
        if line.startswith("Vlan"):
            vlan_line = line
    
    # VLAN interface must exist throughout test
    pytest_assert(vlan_line, "VLAN interface is not configured on the DUT")

    # Gets the status info from the dataline and ensures the VLAN interface is active
    data = vlan_line.split()
    pytest_assert(data[2] == "up/up", "VLAN interface is down when it should be up!")

def get_vlan_interfaces(duthost):
    """Returns list of interfaces attached to the VLAN interface on the DUT (and their statuses)"""

    # Gets information on the VLAN interface
    output_lines = duthost.command("show vlan config")["stdout_lines"]

    # Goes through each line and adds the interface to the return list. Skips first two header lines.
    attached_interfaces = []
    interface_statuses = []

    for line in output_lines[2:]:
        interface_name = line.split()[2]
        interface_statuses.append(get_interface_status(duthost, interface_name))
        attached_interfaces.append(interface_name)
    
    return attached_interfaces, interface_statuses

def test_no_autostate_vlan(duthosts, rand_one_dut_hostname):
    """Makes sure that even if all members of the VLAN interface are down, the VLAN interface itself stays up"""

    duthost = duthosts[rand_one_dut_hostname]

    # Checks initial VLAN state. Should fail if VLAN interface is missing or down.
    check_vlan_state(duthost)

    # Gets list of interfaces attached to VLAN
    attached_interfaces, interface_statuses = get_vlan_interfaces(duthost)

    # Shutsdown all attached and confirms their down status
    for interface_name in attached_interfaces:
        duthost.command("sudo config interface shutdown {}".format(interface_name))
        pytest_assert(not get_interface_status(duthost, interface_name), "Interface {} failed to shutdown".format(interface_name))
    
    # Checks status of VLAN after all attached interfaces have been shut down. Should fail if VLAN interface is missing or down.
    check_vlan_state(duthost)

    # Returns all interfaces to their states prior to test and confirms their status
    for interface_name, status in zip(attached_interfaces, interface_statuses):
        if not status:
            pytest_assert(not get_interface_status(duthost, interface_name), "Interface {} is up when it should be down after test.".format(interface_name))
        else:
            duthost.command("sudo config interface startup {}".format(interface_name))
            pytest_assert(get_interface_status(duthost, interface_name), "Interface {} is down when it should be up after test.".format(interface_name))

