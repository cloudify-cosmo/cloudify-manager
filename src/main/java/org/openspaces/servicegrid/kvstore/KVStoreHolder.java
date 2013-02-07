package org.openspaces.servicegrid.kvstore;


public class KVStoreHolder {

	public static KVStore store = new KVStore();
	
	public static KVStore getStore() {
		return store;
	}

	public static void clear() {
		store.clear();
	}

}
