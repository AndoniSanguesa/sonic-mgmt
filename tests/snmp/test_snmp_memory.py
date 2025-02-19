"""
Test SNMP memory MIB in SONiC.
Parameters:
    --percentage: Set optional percentege of difference for test
"""

import pytest
from tests.common.helpers.assertions import pytest_assert # pylint: disable=import-error
from tests.common.helpers.snmp_helpers import get_snmp_facts
pytestmark = [
    pytest.mark.topology('any')
]

CALC_DIFF = lambda snmp, sys_data: float(abs(snmp - int(sys_data)) * 100) / float(snmp)

@pytest.fixture(autouse=True, scope="module")
def get_parameter(request):
    """
    Get optional parameter percentage or return default 4%
    """
    global percent
    percent = request.config.getoption("--percentage") or 4
    return percent

@pytest.fixture()
def load_memory(duthosts, enum_rand_one_per_hwsku_hostname):
    """
    Execute script in background to load memory
    """
    duthost = duthosts[enum_rand_one_per_hwsku_hostname]
    duthost.copy(src='snmp/memory.py', dest='/tmp/memory.py')
    duthost.shell("nohup python /tmp/memory.py > /dev/null 2>&1 &")
    yield
    duthost.shell("killall python /tmp/memory.py", module_ignore_errors=True)

def collect_memory(duthost):
    """
    Collect memory data from DUT
    """
    facts = {}
    output = duthost.shell("cat /proc/meminfo")['stdout_lines']
    for line in output:
        split = line.split()
        facts.update({split[0].replace(":", ""): split[-2]})
    return facts

def test_snmp_memory(duthosts, enum_rand_one_per_hwsku_hostname, localhost, creds_all_duts):
    """
    Verify if memory MIB equals to data collected from DUT
    """
    duthost = duthosts[enum_rand_one_per_hwsku_hostname]
    host_ip = duthost.host.options['inventory_manager'].get_host(duthost.hostname).vars['ansible_host']
    snmp_facts = get_snmp_facts(localhost, host=host_ip, version="v2c",
                                community=creds_all_duts[duthost]["snmp_rocommunity"], wait=True)['ansible_facts']
    facts = collect_memory(duthost)
    compare = (('ansible_sysTotalFreeMemery', 'MemFree'), ('ansible_sysTotalBuffMemory', 'Buffers'),
               ('ansible_sysCachedMemory', 'Cached'))

    # Verify correct behaviour of sysTotalMemery, sysTotalSharedMemory
    pytest_assert(not abs(snmp_facts['ansible_sysTotalMemery'] - int(facts['MemTotal'])),
                  "Unexpected res sysTotalMemery {}".format(snmp_facts['ansible_sysTotalMemery']))
    pytest_assert(not abs(snmp_facts['ansible_sysTotalSharedMemory'] - int(facts['Shmem'])),
                  "Unexpected res sysTotalSharedMemory {}".format(snmp_facts['ansible_sysTotalSharedMemory']))

    # Verify correct behaviour of sysTotalFreeMemery, sysTotalBuffMemory, sysCachedMemory
    snmp_diff = [snmp for snmp, sys_data in compare if CALC_DIFF(snmp_facts[snmp],
                                                                 facts[sys_data]) > percent]
    pytest_assert(not snmp_diff,
                  "Snmp memory MIBs: {} differs more than {} %".format(snmp_diff, percent))


def test_snmp_memory_load(duthosts, enum_rand_one_per_hwsku_hostname, localhost, creds_all_duts, load_memory):
    """
    Verify SNMP total free memory matches DUT results in stress test
    """
    # Start memory stress generation
    duthost = duthosts[enum_rand_one_per_hwsku_hostname]
    host_ip = duthost.host.options['inventory_manager'].get_host(duthost.hostname).vars['ansible_host']
    snmp_facts = get_snmp_facts(localhost, host=host_ip, version="v2c",
                                community=creds_all_duts[duthost]["snmp_rocommunity"], wait=True)['ansible_facts']
    mem_free = duthost.shell("grep MemFree /proc/meminfo | awk '{print $2}'")['stdout']
    pytest_assert(CALC_DIFF(snmp_facts['ansible_sysTotalFreeMemery'], mem_free) < percent,
                  "sysTotalFreeMemery differs by more than {}".format(percent))
