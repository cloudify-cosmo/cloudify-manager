package org.openspaces.servicegrid.rest.executors;

import java.net.URL;
import java.util.List;
import java.util.Map;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.rest.http.HttpError;
import org.openspaces.servicegrid.rest.http.HttpEtag;
import org.openspaces.servicegrid.rest.http.HttpException;
import org.openspaces.servicegrid.rest.http.NotFoundHttpException;

import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

public class MapTaskExecutorState implements TaskExecutorStateWriter, TaskExecutorStatePollingReader {

	private final Map<URL, List<Object>> objectVersionsById = Maps.newHashMap();
	
	@Override
	public void put(URL executorId, TaskExecutorState state, HttpEtag ifNoneMatchHeader) {
		List<Object> versions = objectVersionsById.get(executorId);
		if (versions == null) {
			versions = Lists.newLinkedList();
			objectVersionsById.put(executorId, versions);
		}
		if (ifNoneMatchHeader != null) {
			verifyEtag(ifNoneMatchHeader, versions);
		}
		versions.add(state);
	}
	
	@Override
	@SuppressWarnings("unchecked")
	public <T> T get(URL executorId) {
		List<Object> versions = objectVersionsById.get(executorId);
		if (versions == null) {
			throw new NotFoundHttpException(executorId);
		}
		T obj = (T) Iterables.getLast(versions, null);
		if (obj == null) {
			throw new NotFoundHttpException(executorId);
		}
		return obj;
	}

	private static void verifyEtag(
			HttpEtag ifNoneMatchHeader,
			List<Object> versions) {
		
		final Object lastVersion = Iterables.getLast(versions, null);
		if (lastVersion == null) {
			if (!ifNoneMatchHeader.equals(HttpEtag.NOT_EXISTS)) {
				throw new HttpException(HttpError.HTTP_CONFLICT);
			}
		} else {
			final HttpEtag lastEtag = newEtag(lastVersion);
			if (!lastEtag.equals(ifNoneMatchHeader)) {
				throw new HttpException(HttpError.HTTP_CONFLICT);
			}
		}
	}

	private static HttpEtag newEtag(Object lastVersion) {
		//TODO: MD5 hash
		return new HttpEtag(String.valueOf(lastVersion.hashCode()));
	}
}
