package org.openspaces.servicegrid;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.state.Etag;
import org.openspaces.servicegrid.state.EtagPreconditionNotMetException;
import org.openspaces.servicegrid.state.EtagState;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import com.sun.jersey.api.client.Client;
import com.sun.jersey.api.client.ClientResponse;
import com.sun.jersey.api.client.ClientResponse.Status;
import com.sun.jersey.api.client.UniformInterfaceException;
import com.sun.jersey.api.client.WebResource;
import com.sun.jersey.api.client.config.ClientConfig;
import com.sun.jersey.api.client.config.DefaultClientConfig;

public class StateClient implements StateReader, StateWriter {
	
	private final ObjectMapper mapper;
	private final URI restUri;
	private WebResource webResource;
	
	public StateClient(URI restUri) {
		this.restUri = restUri;
		mapper = StreamUtils.newObjectMapper();
		final ClientConfig clientConfig = new DefaultClientConfig();
		final Client client = Client.create(clientConfig);
		webResource = client.resource(restUri);		  
	}
	
	@Override
	public Etag put(URI id, Object state, Etag etag) {
		final String path = getPathFromId(id);
		final String json = StreamUtils.toJson(mapper,state);
		ClientResponse response;
		if (etag.equals(Etag.empty())) {
			response = 
				webResource
					.path(path)
					.header("If-None-Match", "*")
					.put(ClientResponse.class, json);
		}
		else {
			response = 
				webResource
					.path(path)
					.header("If-Match", etag.toString())
					.put(ClientResponse.class, json);
		}
		if (response.getClientResponseStatus() == ClientResponse.Status.OK) {
			return Etag.create(response);
		}
		else if (response.getClientResponseStatus()== ClientResponse.Status.PRECONDITION_FAILED) {
			throw new EtagPreconditionNotMetException(Etag.create(response), etag);
		}
		throw new UniformInterfaceException(response);
	}

	@Override
	public <T> EtagState<T> get(URI id, Class<? extends T> clazz) {
		final String path = getPathFromId(id);
		
		ClientResponse response = webResource.path(path).get(ClientResponse.class);
		Status status = response.getClientResponseStatus();
		if (status == ClientResponse.Status.OK) {
			String json = response.getEntity(String.class);
			Etag etag = Etag.create(response);
			final T state = StreamUtils.fromJson(mapper, json, clazz);
			return new EtagState<T>(etag, state);
		}
		else if (status == ClientResponse.Status.NOT_FOUND) {
			return null;
		}
		else {
			throw new UniformInterfaceException(response);
		}
	}
	
	private String getPathFromId(URI id) {
		Preconditions.checkArgument(id.toString().startsWith(restUri.toString()));
		return StreamUtils.fixSlash(id.toString().substring(restUri.toString().length()));
	}

	public boolean stateEquals(TaskConsumerState state1, TaskConsumerState state2) {
		return StreamUtils.elementEquals(mapper, state1, state2);
	}

	@Override
	public Iterable<URI> getElementIdsStartingWith(final URI idPrefix) {
		final String path = getPathFromId(idPrefix)+"*/_list";
		final String json = webResource.path(path).get(String.class);
		@SuppressWarnings("unchecked")
		final List<String> uris = StreamUtils.fromJson(mapper, json, List.class);
		return Iterables.transform(uris, new Function<String,URI>(){

			@Override
			public URI apply(String uri) {
				return StreamUtils.newURI(uri);
			}});
	}

}
