package org.openspaces.servicegrid.rest.executors;

import java.net.URL;

public interface TaskExecutorStatePollingReader {

	<T> T get(URL id);
}
