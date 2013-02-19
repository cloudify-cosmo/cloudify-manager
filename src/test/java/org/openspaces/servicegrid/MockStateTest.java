/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *       http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
package org.openspaces.servicegrid;

import java.lang.reflect.Method;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.logging.Logger;


import org.openspaces.servicegrid.kvstore.KVStoreServer;
import org.openspaces.servicegrid.mock.MockState;
import org.openspaces.servicegrid.state.Etag;
import org.openspaces.servicegrid.state.EtagPreconditionNotMetException;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.testng.Assert;
import org.testng.annotations.AfterClass;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.fasterxml.jackson.databind.ObjectMapper;

public class MockStateTest {
	
	private static final int PORT = 8080;
	private static final URI STATE_SERVER_URI = StreamUtils.newURI("http://localhost:"+PORT+"/");
	
	final URI id = StreamUtils.newURI("http://localhost:"+PORT+"/services/tomcat");
	final ObjectMapper mapper = StreamUtils.newObjectMapper();
	private final Logger logger = Logger.getLogger(this.getClass().getName());
	
	private final boolean useMock = false;
	
	private KVStoreServer stateServer;
	
	StateReader stateReader;
	StateWriter stateWriter;
	
	@BeforeClass
	public void beforeClass() {
		if (useMock) {
			stateReader = new MockState();
			stateWriter = (StateWriter) stateReader;
		}
		else {
			stateReader = new StateClient(STATE_SERVER_URI);
			stateWriter = (StateWriter) stateReader;
			stateServer = new KVStoreServer();
			stateServer.start(PORT);
		}
	}
	
	@AfterClass
	public void afterClass() {
		if (!useMock) {
			stateServer.stop();
		}
	}
	
	@BeforeMethod
	public void beforeMethod(Method method) {
		if (useMock) {
			((MockState)stateWriter).clear();
		}
		else {
			stateServer.reload();
		}
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

	@Test
	public void testSecondPutBadEtag() throws URISyntaxException {
		final TaskConsumerState taskConsumerState1 = new TaskConsumerState();
		final TaskConsumerState taskConsumerState2 = new TaskConsumerState();
		taskConsumerState2.setProperty("kuku", "loko");
		Etag etag1 = stateWriter.put(id, taskConsumerState1, Etag.EMPTY);
		try {
			stateWriter.put(id, taskConsumerState2, Etag.EMPTY);
			Assert.fail("Expected exception");
		}
		catch (EtagPreconditionNotMetException e) {
			Assert.assertEquals(e.getResponseEtag(), etag1);
			Assert.assertEquals(e.getRequestEtag(), Etag.EMPTY);
		}
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
