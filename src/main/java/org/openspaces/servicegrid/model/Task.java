package org.openspaces.servicegrid.model;

import java.util.Map;
import java.util.Set;

import com.google.common.collect.Maps;
import com.google.common.collect.Sets;

public class Task {

	private String type;
	private final Map<String,Object> properties = Maps.newHashMap();
	private Set<String> tags = Sets.newHashSet();
	private String target;
	private TaskId id;

	public String getType() {
		return type;
	}

	public void setType(String type) {
		this.type = type;	
	}

	public void setProperty(String key, Object value) {
		this.properties.put(key, value);
	}

	public <T> T getProperty(String key, Class<? extends T> clazz) {
		return (T) properties.get(key);
	}

	public void setTags(Set<String> tags) {
		this.tags = tags;
	}

	public Set<String> getTags() {
		return this.tags;
	}

	public void setTarget(String target) {
		this.target = target;
	}
	
	public String getTarget() {
		return target;
	}

	public TaskId getId() {
		return id;
	}

	public void setId(TaskId id) {
		this.id = id;
	}
}
