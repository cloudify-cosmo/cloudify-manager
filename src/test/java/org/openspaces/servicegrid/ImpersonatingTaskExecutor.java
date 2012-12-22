package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface ImpersonatingTaskExecutor<S1 extends TaskExecutorState,S2 extends TaskExecutorState> extends TaskExecutor<S1> {

	ServiceInstanceState getImpersonatedState();

}
