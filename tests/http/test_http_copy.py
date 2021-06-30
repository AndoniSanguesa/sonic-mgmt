import os
import pytest
import paramiko
import hashlib
from scp import SCPClient

pytestmark = [
    pytest.mark.disable_loganalyzer,
    pytest.mark.topology("any"),
    pytest.mark.device_type("vs"),
]

SONIC_SSH_PORT = 22
SONIC_SSH_REGEX = "OpenSSH_[\\w\\.]+ Debian"


def test_http_copy(duthosts, rand_one_dut_hostname, localhost):
    """Test that HTTP (copy) can be used to download objects to the DUT"""

    duthost = duthosts[rand_one_dut_hostname]
    dut_mgmt_ip = duthost.mgmt_ip

    test_img = "sonic-build.azurewebsites.net/api/sonic/artifacts?branchName=master\&platform=vs\&target=target/sonic-vs.img.gz"
    test_img_file_name = "sonic-vs.img.gz"

    # Check that SSH port is open on the DUT
    res = localhost.wait_for(
        host=dut_mgmt_ip,
        port=SONIC_SSH_PORT,
        state="started",
        search_regex=SONIC_SSH_REGEX,
        delay=0,
        timeout=20,
        module_ignore_errors=True,
    )

    if res.is_failed:
        pytest.fail("SSH port is not open on the DUT.")

    # Download file via http into temp directory
    os.system("sudo wget {} -O /tmp/{}".format(test_img, test_img_file_name))

    # Generate MD5 checksum to compare the sent file to
    with open("/tmp/{}".format(test_img_file_name)) as file:
        orig_checksum = hashlib.md5(file.read()).hexdigest()

    # Set up ssh client for dut
    ssh_cli = paramiko.SSHClient()
    ssh_cli.load_system_host_keys()
    ssh_cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_cli.connect("10.250.0.101", 22, "admin", "password")

    # Create scp client
    scp_cli = SCPClient(ssh_cli.get_transport())

    # Send file to dut via scp
    scp_cli.put("/tmp/{}".format(test_img_file_name), remote_path="~/")

    # Validate file was sent
    res = duthost.command("ls -ltr ~/{}".format(test_img_file_name))["rc"]

    if res != 0:
        pytest.fail("Test file was not found on DUT after attempted scp copy")

    # Remove local version of the file
    os.system("sudo rm /tmp/{}".format(test_img_file_name))

    # Ensure that file was removed correctly
    if os.path.isfile("/tmp/{}".format(test_img_file_name)):
        pytest.fail("Host machine could not be cleaned")

    # Request back sent file
    scp_cli.get("~/{}".format(test_img_file_name), local_path="/tmp/")

    # Get checksum of received file
    with open("/tmp/{}".format(test_img_file_name)) as file:
        new_checksum = hashlib.md5(file.read()).hexdigest()

    # Confirm that the received file is identical to the original file
    if orig_checksum != new_checksum:
        pytest.fail("Original file differs from file ssh'ed to the DUT and back.")

    # Perform cleanup on DUT
    duthost.command("sudo rm !/{}".format(test_img_file_name))

    # Confirm cleanup occured succesfuly
    res = duthost.command("ls -ltr ~/{}".format(test_img_file_name))["rc"]
    if res == 0:
        pytest.fail("DUT could not be cleaned.")
