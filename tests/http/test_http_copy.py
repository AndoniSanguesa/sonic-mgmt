import os
import pytest
import hashlib
import time
import subprocess
import sys

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

    test_img = "sonic-build.azurewebsites.net/api/sonic/artifacts?branchName=master\&platform=vs\&target=target/sonic-vs.img.gz"
    test_img_file_name = "sonic-vs.img.gz"

    # Start HTTP Server
    pid = subprocess.Popen([sys.executable, "./http/start_http_server.py"])

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

    # Download file via http into current dir
    os.system("sudo wget {} -O ./http/{}".format(test_img, test_img_file_name))

    # Ensure that file was downloaded
    if not os.path.isfile("./http/{}".format(test_img_file_name)):
        pytest.fail("file could not be downloaded to host machine")

    # Generate MD5 checksum to compare with the sent file
    with open("./http/{}".format(test_img_file_name)) as file:
        orig_checksum = hashlib.md5(file.read()).hexdigest()

    # Have DUT request file from http server
    duthost.command("curl -O {}:{}/http/{}".format(CONTAINER_IP, HTTP_PORT, test_img_file_name))

    # Validate file was received
    res = duthost.command("ls -ltr ./{}".format(test_img_file_name), module_ignore_errors=True)["rc"]

    if res != 0:
        pytest.fail("Test file was not found on DUT after attempted scp copy")

    # Get MD5 checksum of received file
    output = duthost.command("md5sum ./{}".format(test_img_file_name))["stdout"]
    new_checksum = output.split()[0]

    # Confirm that the received file is identical to the original file
    if orig_checksum != new_checksum:
        pytest.fail("Original file differs from file ssh'ed to the DUT and back.")

    # Perform cleanup on DUT
    duthost.command("sudo rm /home/admin/{}".format(test_img_file_name))

    # Confirm cleanup occured succesfuly
    res = duthost.command("ls -ltr ./{}".format(test_img_file_name), module_ignore_errors=True)["rc"]
    if res == 0:
        pytest.fail("DUT could not be cleaned.")

    # Delete file off host
    os.system("sudo rm ./http/{}".format(test_img_file_name))

    # Ensure that file was removed correctly
    if os.path.isfile("./http/{}".format(test_img_file_name)):
        pytest.fail("Host machine could not be cleaned")

    # Stop HTTP server
    pid.kill()

    # Ensure that HTTP server was closed
    started = True
    tries = 0
    while started and tries < 10:
        if os.system("curl localhost:8080") != 0:
            started = False
        tries += 1
        time.sleep(1)

    if started == True:
        pytest.fail("HTTP Server could not be stopped.")