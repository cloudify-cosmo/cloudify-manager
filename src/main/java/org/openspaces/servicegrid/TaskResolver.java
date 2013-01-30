package org.openspaces.servicegrid;

import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;

import com.fasterxml.jackson.annotation.JsonTypeInfo.Id;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.jsontype.TypeIdResolver;
import com.fasterxml.jackson.databind.type.SimpleType;
import com.google.common.base.CaseFormat;
import com.google.common.base.Preconditions;

public class TaskResolver implements TypeIdResolver {

	private static final String[] prefixes = new String[] { 
		InstallServiceTask.class.getPackage().getName()+".", PingAgentTask.class.getPackage().getName()+".", TaskProducerTask.class.getPackage().getName()+"."};
	
	private String postfix = "Task";
	
	@Override
	public void init(JavaType baseType) {

	}

	@Override
	public String idFromValue(Object value) {
		return fromUpperCamel(removePostfix(removePackage(value.getClass())));
	}

	@Override
	public String idFromValueAndType(Object value, Class<?> suggestedType) {
		return fromUpperCamel(removePostfix(removePackage(value.getClass())));
	}

	@Override
	public String idFromBaseType() {
		return Task.class.getName();
	}

	@Override
	public JavaType typeFromId(String id) {
		return SimpleType.construct(addPackage(addPostfix(toUpperCamel(id))));
	}

	@Override
	public Id getMechanism() {
		return Id.CLASS;
	}
	
	private String addPostfix(String id) {
		return id + postfix;
	}

	private String removePostfix(String name) {
		Preconditions.checkArgument(name.endsWith(postfix));
		name = name.substring(0, name.length() - postfix.length());
		return name;
	}
	
	private String removePackage(Class<?> clazz) {
		final String name = clazz.getName();
		String nameWithoutPrefix = null;
		for (String prefix : prefixes) {
			if (name.startsWith(prefix)) {
				nameWithoutPrefix = name.substring(prefix.length());
				break;
			}
		}
		Preconditions.checkArgument(nameWithoutPrefix != null, "Unknwon package of class %s", name);
		
		return nameWithoutPrefix;
	}
	
	private Class<?> addPackage(String className) {
		Class<?> clazz = null;
		for (String prefix : prefixes) {
			try {
				clazz = Class.forName(prefix+className);
				break;
			} catch (ClassNotFoundException e) {
				
			} catch (NoClassDefFoundError e) {
				
			}
		}
		
		Preconditions.checkArgument(clazz != null, "Cannot determine full class name of %s", className);
		return clazz;
	}
	
	
	private String fromUpperCamel(String id) {
		return CaseFormat.UPPER_CAMEL.to(CaseFormat.LOWER_UNDERSCORE, id);
	}
	
	private String toUpperCamel(String id) {
		return CaseFormat.LOWER_UNDERSCORE.to(CaseFormat.UPPER_CAMEL, id);
	}
}

