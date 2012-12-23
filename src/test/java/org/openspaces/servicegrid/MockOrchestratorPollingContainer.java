package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;


public class MockOrchestratorPollingContainer extends MockTaskPolling {
	
	private StreamProducer<Task> taskProducer;

	public MockOrchestratorPollingContainer(
			URL orchestratorId,
			StreamProducer<TaskExecutorState> stateWriter, 
			StreamConsumer<Task> taskConsumer,
			StreamProducer<Task> taskProducer,
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
			taskProducer.addElement(newTask.getTarget(), newTask);
		}
	}
	
}
