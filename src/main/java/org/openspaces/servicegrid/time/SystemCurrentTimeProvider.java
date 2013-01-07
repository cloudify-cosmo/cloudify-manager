package org.openspaces.servicegrid.time;

public class SystemCurrentTimeProvider implements CurrentTimeProvider {

	@Override
	public long currentTimeMillis() {
		return System.currentTimeMillis();
	}

}
