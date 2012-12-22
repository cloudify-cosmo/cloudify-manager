package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.rest.HttpEtag;

public interface TaskExecutorStateWriter {
	
	void put(URL id, TaskExecutorState object, HttpEtag etag);
}
