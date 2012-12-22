package org.openspaces.servicegrid;

import java.net.URL;

public interface TaskExecutorStatePollingReader {

	<T> T get(URL id);
}
