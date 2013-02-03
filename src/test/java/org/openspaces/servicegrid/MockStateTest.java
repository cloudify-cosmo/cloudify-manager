package org.openspaces.servicegrid;

import java.net.URI;
import java.net.URISyntaxException;

import junit.framework.Assert;

import org.openspaces.servicegrid.mock.MockState;
import org.openspaces.servicegrid.state.Etag;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.testng.annotations.Test;

import com.fasterxml.jackson.databind.ObjectMapper;

public class MockStateTest {

	final URI id = StreamUtils.newURI("http://localhost/services/tomcat");
	final ObjectMapper mapper = StreamUtils.newObjectMapper();
	
	@Test
	public void testFirstPut() throws URISyntaxException {
		final MockState state = new MockState();
		final TaskConsumerState taskConsumerState = new TaskConsumerState();
		final Etag etag = state.put(id, taskConsumerState, Etag.EMPTY);
		Assert.assertFalse(Etag.EMPTY.equals(etag));
		
		assertEqualsState(taskConsumerState, state.get(id, TaskConsumerState.class).getState());
	}

	@Test
	public void testSecondPut() throws URISyntaxException {
		final MockState state = new MockState();
		final TaskConsumerState taskConsumerState1 = new TaskConsumerState();
		final TaskConsumerState taskConsumerState2 = new TaskConsumerState();
		taskConsumerState2.setProperty("kuku", "loko");
		
		final Etag etag1 = state.put(id, taskConsumerState1, Etag.EMPTY);
		final Etag etag2 = state.put(id, taskConsumerState2, etag1);
		Assert.assertFalse(etag1.equals(etag2));
		assertEqualsState(taskConsumerState2, state.get(id, TaskConsumerState.class).getState());
	}

	@Test(expectedExceptions = IllegalArgumentException.class)
	public void testSecondPutBadEtag() throws URISyntaxException {
		final MockState state = new MockState();
		final TaskConsumerState taskConsumerState1 = new TaskConsumerState();
		final TaskConsumerState taskConsumerState2 = new TaskConsumerState();
		taskConsumerState2.setProperty("kuku", "loko");
		state.put(id, taskConsumerState1, Etag.EMPTY);
		state.put(id, taskConsumerState2, Etag.EMPTY);
	}
	
	private void assertEqualsState(
			TaskConsumerState expectedState,
			TaskConsumerState actualState) {
		Assert.assertTrue(StreamUtils.elementEquals(mapper, expectedState, actualState));
	}
	
	@Test
	public void testEmptyGet() throws URISyntaxException {
		final MockState state = new MockState();
		Assert.assertEquals(null, state.get(id, TaskConsumerState.class));
	}
}
