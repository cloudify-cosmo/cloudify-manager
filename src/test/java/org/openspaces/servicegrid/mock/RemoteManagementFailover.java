package org.openspaces.servicegrid.mock;

/**
 * Indicates that {@link MockTaskContainer} has detected that management state or history is erased.
 * @author itaif
 *
 */
public class RemoteManagementFailover extends RuntimeException {

	public RemoteManagementFailover(IllegalArgumentException e) {
		
	}

}
