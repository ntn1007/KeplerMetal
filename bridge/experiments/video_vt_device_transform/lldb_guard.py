# SPDX-License-Identifier: MIT
"""Do not quit LLDB while its controlled target has an unresolved state."""
import time
import lldb


def await_terminal(debugger):
    process = debugger.GetSelectedTarget().GetProcess()
    if not process.IsValid() or not process.GetProcessID():
        print('KP_GUARD_NO_PROCESS', flush=True)
        return
    reported = False
    while process.GetState() != lldb.eStateExited:
        if not reported:
            print('KP_GUARD_UNRESOLVED pid=%d state=%d' %
                  (process.GetProcessID(), process.GetState()), flush=True)
            reported = True
        time.sleep(5)
    print('KP_PROCESS_EXITED pid=%d code=%d' %
          (process.GetProcessID(), process.GetExitStatus()), flush=True)
