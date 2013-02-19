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

import org.reflections.Reflections;

import com.fasterxml.jackson.annotation.JsonTypeInfo.Id;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.jsontype.TypeIdResolver;
import com.fasterxml.jackson.databind.type.SimpleType;
import com.google.common.base.CaseFormat;
import com.google.common.base.Preconditions;
import com.google.common.collect.BiMap;
import com.google.common.collect.HashBiMap;

public class TaskTypeIdResolver implements TypeIdResolver {

	private static BiMap<String, Class<?>> idResolver = HashBiMap.create();
	
	static {
		final Reflections reflections = new Reflections("org.openspaces.servicegrid");
		registerPojoTypes(reflections, Task.class);
	}
	
	private static void registerPojoTypes(Reflections reflections, Class<?> type) {
		
		TaskTypeIdResolver.registerType(type);
		for (final Class<?> taskType : reflections.getSubTypesOf(type)) {
			TaskTypeIdResolver.registerType(taskType);
		}	
	}
	
	private JavaType baseType;
	
	@Override
	public void init(JavaType baseType) {
		this.baseType = baseType;
	}

	@Override
	public String idFromValue(Object value) {
		synchronized(idResolver) {
			String id = idResolver.inverse().get(value.getClass());
			Preconditions.checkArgument(id != null, "Cannot resolve id for class %s", value.getClass());
			return id;
		}
	}

	@Override
	public String idFromValueAndType(Object value, Class<?> suggestedType) {
		return idFromValue(value);
	}

	@Override
	public String idFromBaseType() {
		Preconditions.checkState(baseType != null);
		return classToId(baseType.getRawClass());
	}

	@Override
	public Id getMechanism() {
		return Id.CUSTOM;
	}
	
	public static void registerType(Class<?> clazz) {
		Preconditions.checkNotNull(clazz);
		synchronized(idResolver) {
			
			final String id = classToId(clazz);
			final Class<?> registeredClass = idResolver.get(id);
			
			if (registeredClass == null) {
				idResolver.put(id, clazz);
			}
			else {
				Preconditions.checkArgument(
						registeredClass.equals(clazz), 
						"Cannot register type %s since it conflicts with %s",clazz.getName(), registeredClass.getName());	
			}
		}
	}

	private static String classToId(Class<?> clazz) {
		return CaseFormat.UPPER_CAMEL.to(CaseFormat.LOWER_UNDERSCORE, clazz.getSimpleName());
	}

	@Override
	public JavaType typeFromId(String id) {
		synchronized(idResolver) {
			Class<?> clazz = idResolver.get(id);
			Preconditions.checkArgument(clazz != null, "Cannot convert id %s into a class", id);
			return SimpleType.construct(clazz);
		}
	}
}
