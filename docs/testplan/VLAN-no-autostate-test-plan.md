# VLAN No Autostate Test Plan

- [Overview](#overview)
    - [Scope](#scope)
- [Test Procedure](#test-procedure)

## Overview
the purpose of this test is to make sure that the VLAN interface stays up even if there are no active interfaces attached to it.

### Scope
This test was verified on a t0 topology, but should work on any other topology since the only config commands being run are on the DUT and are independent of any leaf nodes.

## Test Procedure

1. Confirm that the VLAN interface is configured. If it is not, the test fails
2. Check that the VLAN interface's administrative status is 'up'. If it is not, the test fails
3. A list of the interfaces attached to the VLAN is generated
    - The status for each of these interfaces is recorded so that they can be returned to their original state after the test.
4. Each interface attached to the VLAN is shut down. Their down status is confirmed. If any interfaces are still up, the test fails.
5. Check that the VLAN interface's administrative status is still 'up'. If it is not, the test fails.
6. All ports are returned to their state prior to the test as recorded in step 3.
    - If any tests fail to be returned to the original state the test fails.