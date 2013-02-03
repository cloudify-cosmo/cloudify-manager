package org.openspaces.servicegrid;

import java.net.URI;

public interface TaskReader {

	<T extends Task> T removeNextTask(URI taskConsumerId);

	Iterable<Task> getPendingTasks(URI taskConsumerId);
}
