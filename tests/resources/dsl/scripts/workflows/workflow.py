from cloudify.workflows import ctx

instance = next(ctx.get_node('node').instances)
op2_result = instance.execute_operation('test.op2').get()
instance.execute_operation('test.op1', kwargs={'property': op2_result})
