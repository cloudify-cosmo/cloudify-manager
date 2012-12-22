package org.openspaces.servicegrid.rest.executors;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.rest.http.HttpEtag;

public interface TaskExecutorStateWriter {
	
	void put(URL id, TaskExecutorState object, HttpEtag etag);
}
