import os
import pytest
import paramiko
import hashlib
import time
import subprocess
import sys
from scp import SCPClient

pytestmark = [
    pytest.mark.disable_loganalyzer,
    pytest.mark.topology("any"),
    pytest.mark.device_type("vs"),
]

SONIC_SSH_PORT = 22
SONIC_SSH_REGEX = "OpenSSH_[\\w\\.]+ Debian"
CONTAINER_IP = "172.17.0.2"
HTTP_PORT = "8080"

def test_http_copy(duthosts, rand_one_dut_hostname, localhost):
    """Test that HTTP (copy) can be used to download objects to the DUT"""
    
    duthost = duthosts[rand_one_dut_hostname]
    dut_mgmt_ip = duthost.mgmt_ip

    test_img = "sonic-build.azurewebsites.net/api/sonic/artifacts?branchName=master\&platform=vs\&target=target/sonic-vs.img.gz"
    test_img_file_name = "sonic-vs.img.gz"

    # Download file via http into current dir
    os.system("sudo wget {} -O {}".format(test_img, test_img_file_name))

    # Generate MD5 checksum to compare with the sent file
    with open("{}".format(test_img_file_name)) as file:
        orig_checksum = hashlib.md5(file.read()).hexdigest()

    # Start HTTP Server
    pid = subprocess.Popen([sys.executable, "start_http_server.py"])

    # Validate HTTP Server has started
    started = False
    tries = 0
    while not started and tries < 10:
        if os.system("curl localhost:8080") == 0:
            started = True
        tries += 1
        time.sleep(1)

    if not started:
        pytest.fail("HTTP Server could not be started")

    # Have DUT request file from http server
    duthost.command("curl -O {}:{}/{}".format(CONTAINER_IP, HTTP_PORT, test_img_file_name))

    # Validate file was received
    res = duthost.command("ls -ltr ~/{}".format(test_img_file_name))["rc"]

    if res != 0:
        pytest.fail("Test file was not found on DUT after attempted scp copy")

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

    # Set up ssh client for dut
    ssh_cli = paramiko.SSHClient()
    ssh_cli.load_system_host_keys()
    ssh_cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_cli.connect("10.250.0.101", 22, "admin", "password")

    # Create scp client
    scp_cli = SCPClient(ssh_cli.get_transport())

    # Remove local version of the file
    os.system("sudo rm {}".format(test_img_file_name))

    # Ensure that file was removed correctly
    if os.path.isfile("{}".format(test_img_file_name)):
        pytest.fail("Host machine could not be cleaned")

    # Request back sent file
    scp_cli.get("~/{}".format(test_img_file_name))

    # Get MD5 checksum of received file
    with open("{}".format(test_img_file_name)) as file:
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

    # Delete file off host
    os.system("sudo rm {}".format(test_img_file_name))

    # Ensure that file was removed correctly
    if os.path.isfile("{}".format(test_img_file_name)):
        pytest.fail("Host machine could not be cleaned")

    # Stop HTTP server
    pid.kill()

    # Ensure that HTTP server was closed
    started = True
    tries = 0
    while not started and tries < 10:
        if os.system("curl localhost:8080") != 0:
            started = False
        tries += 1
        time.sleep(1)

    if started == True:
        pytest.fail("HTTP Server could not be stopped.")