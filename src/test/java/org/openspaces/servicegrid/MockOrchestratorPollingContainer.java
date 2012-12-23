package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.rest.executors.TaskExecutorStateWriter;
import org.openspaces.servicegrid.rest.tasks.StreamConsumer;
import org.openspaces.servicegrid.rest.tasks.StreamProducer;

import com.google.common.base.Preconditions;


public class MockOrchestratorPollingContainer extends MockTaskPolling {
	
	private StreamProducer taskProducer;

	public MockOrchestratorPollingContainer(
			URL orchestratorId,
			TaskExecutorStateWriter stateWriter, 
			StreamConsumer taskConsumer,
			StreamProducer taskProducer,
			Orchestrator<? extends TaskExecutorState> orchetrator) {
	
		super(orchestratorId, stateWriter, taskConsumer, orchetrator);
		this.taskProducer = taskProducer;
	}

	public void stepOrchestrator() {
		
		Orchestrator<? extends TaskExecutorState> orchetrator =
				(Orchestrator<? extends TaskExecutorState>) super.getTaskExecutor();
		
		Iterable<? extends Task> newTasks = orchetrator.orchestrate();
		for (Task newTask : newTasks) {
			newTask.setSource(super.getExecutorId());
			Preconditions.checkNotNull(newTask.getTarget());
			taskProducer.addToStream(newTask.getTarget(), newTask);
		}
	}
	
}
