package org.openspaces.servicegrid;


public interface TaskWriter {
	
	/**
	 * @param task - Adds a task to be processed by task.getConsumerId()
	 * @return true - if added, false - if exact same task already in the queue (ignoring producer timestamp)
	 */
	boolean postNewTask(Task task);
}
