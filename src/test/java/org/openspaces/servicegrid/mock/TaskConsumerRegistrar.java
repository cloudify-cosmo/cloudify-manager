package org.openspaces.servicegrid.mock;

import java.net.URI;

public interface TaskConsumerRegistrar {
	
	/**
	 * Registers the task consumer with the specified id.
	 */
	void registerTaskConsumer(Object taskConsumer, URI taskConsumerId);

	/**
	 * Unregisters a task consumer with the specified id.
	 * @return The task consumer object
	 */
	Object unregisterTaskConsumer(URI taskConsumerId);
	
}
