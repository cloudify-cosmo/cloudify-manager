from cloudify.decorators import system_wide_workflow


@system_wide_workflow
def create(ctx, snapshot_id, **kwargs):
    pass
