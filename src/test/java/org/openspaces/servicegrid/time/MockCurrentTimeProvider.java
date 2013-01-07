package org.openspaces.servicegrid.time;

import java.util.concurrent.atomic.AtomicLong;

public class MockCurrentTimeProvider implements CurrentTimeProvider {

	private AtomicLong currentTime = new AtomicLong();
	
	public void increaseBy(long increaseTimeMillis) {
		currentTime.addAndGet(increaseTimeMillis);
	}

	@Override
	public long currentTimeMillis() {
		return currentTime.get();
	}
}
