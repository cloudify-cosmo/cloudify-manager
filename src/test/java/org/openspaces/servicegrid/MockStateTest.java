package org.openspaces.servicegrid;

import java.lang.reflect.Method;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.logging.Logger;

import junit.framework.Assert;

import org.openspaces.servicegrid.mock.MockState;
import org.openspaces.servicegrid.state.Etag;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.fasterxml.jackson.databind.ObjectMapper;

public class MockStateTest {

	final URI id = StreamUtils.newURI("http://localhost/services/tomcat");
	final ObjectMapper mapper = StreamUtils.newObjectMapper();
	private final Logger logger = Logger.getLogger(this.getClass().getName());
	
	StateReader stateReader;
	StateWriter stateWriter;
	
	@BeforeMethod
	public void beforeMethod(Method method) {
		stateReader = new MockState();
		stateWriter = (StateWriter) stateReader;
		logger.info("Starting " + method.getName());
	}

	@Test
	public void testFirstPut() throws URISyntaxException {
		final TaskConsumerState taskConsumerState = new TaskConsumerState();
		final Etag etag = stateWriter.put(id, taskConsumerState, Etag.EMPTY);
		Assert.assertFalse(Etag.EMPTY.equals(etag));
		
		assertEqualsState(taskConsumerState, stateReader.get(id, TaskConsumerState.class).getState());
	}

	@Test
	public void testSecondPut() throws URISyntaxException {
		final TaskConsumerState taskConsumerState1 = new TaskConsumerState();
		final TaskConsumerState taskConsumerState2 = new TaskConsumerState();
		taskConsumerState2.setProperty("kuku", "loko");
		
		final Etag etag1 = stateWriter.put(id, taskConsumerState1, Etag.EMPTY);
		final Etag etag2 = stateWriter.put(id, taskConsumerState2, etag1);
		Assert.assertFalse(etag1.equals(etag2));
		assertEqualsState(taskConsumerState2, stateReader.get(id, TaskConsumerState.class).getState());
	}

	@Test(expectedExceptions = IllegalArgumentException.class)
	public void testSecondPutBadEtag() throws URISyntaxException {
		final TaskConsumerState taskConsumerState1 = new TaskConsumerState();
		final TaskConsumerState taskConsumerState2 = new TaskConsumerState();
		taskConsumerState2.setProperty("kuku", "loko");
		stateWriter.put(id, taskConsumerState1, Etag.EMPTY);
		stateWriter.put(id, taskConsumerState2, Etag.EMPTY);
	}
	
	private void assertEqualsState(
			TaskConsumerState expectedState,
			TaskConsumerState actualState) {
		Assert.assertTrue(StreamUtils.elementEquals(mapper, expectedState, actualState));
	}
	
	@Test
	public void testEmptyGet() throws URISyntaxException {
		Assert.assertEquals(null, stateReader.get(id, TaskConsumerState.class));
	}
}
