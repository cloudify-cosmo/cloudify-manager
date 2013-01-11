package org.openspaces.servicegrid.mock;

import java.net.URI;

public interface TaskConsumerRegistrar {
	
	void registerTaskConsumer(Object taskConsumer, URI executorId);

	void unregisterTaskConsumer(URI executorId);
	
}
