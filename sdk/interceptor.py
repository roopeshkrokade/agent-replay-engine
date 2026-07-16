from typing import Any, Callable
from runtime import ReplayVM

class ReplayInterceptor:
    """
    Intercepts application SDK calls and routes them to the ReplayVM.
    """
    def __init__(self, vm: ReplayVM):
        self.vm = vm

    def patch(self, target_obj: Any, method_name: str, input_mapper: Callable):
        """
        Monkey-patches a method on an object to route through the VM.
        `input_mapper` translates the SDK's raw arguments into our VM's expected dictionary format.
        """
        original_method = getattr(target_obj, method_name)

        def intercepted_call(*args, **kwargs):
            print(f"  🕵️ [Interceptor] Caught call to '{method_name}'")
            
            # 1. Map SDK args to our VM's expected input payload
            vm_input = input_mapper(*args, **kwargs)
            
            # 2. Advance the VM
            result = self.vm.advance(vm_input)
            
            if not result.success:
                raise RuntimeError(f"Replay Divergence: {result.resolution.reason}")
                
            print(f"  ✨ [Interceptor] Returning deterministic cached response for node '{result.resolution.node_id}'")
            
            # 3. Return the historical output instead of making a network call
            return result.output

        setattr(target_obj, method_name, intercepted_call)
        return original_method