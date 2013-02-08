package org.openspaces.servicegrid.kvstore;

import javax.ws.rs.core.EntityTag;

import com.google.common.hash.Hashing;

public class KVEntityTag {
	
	public static EntityTag create(String input) {
		return new EntityTag(Hashing.md5().hashString(input).toString());
	}
	
}
