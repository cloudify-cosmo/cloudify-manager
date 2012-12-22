package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;

public interface TaskProducer {

	URL post(URL executorId, Task object);
}
