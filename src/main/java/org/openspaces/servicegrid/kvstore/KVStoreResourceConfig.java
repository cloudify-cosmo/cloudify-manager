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
 *******************************************************************************/
package org.openspaces.servicegrid.kvstore;

import java.lang.reflect.Type;

import javax.ws.rs.core.Context;

import com.sun.jersey.api.core.PackagesResourceConfig;
import com.sun.jersey.core.spi.component.ComponentContext;
import com.sun.jersey.core.spi.component.ComponentScope;
import com.sun.jersey.spi.inject.Injectable;
import com.sun.jersey.spi.inject.InjectableProvider;

/**
 * Servlet configuration that injects the kvstore.
 * When servlet reloads, the old servlet keeps processing old requests based on the old kvstore.
 * So this configuration creates a new kvsore for the new servlet.
 * 
 * Use "@Context KVStore kvstore" in the servlet, to get the injected kvstore singleton. 
 * @author itaif
 *
 */
public class KVStoreResourceConfig extends PackagesResourceConfig {

	private static final String SCAN_SERVLET_PACKAGE = KVStoreServlet.class.getPackage().getName();
	
	KVStoreInjectableProvider kvStoreProvider;
	
	public KVStoreResourceConfig() {
		super(SCAN_SERVLET_PACKAGE);
		kvStoreProvider = new KVStoreInjectableProvider();
		super.getSingletons().add(kvStoreProvider);
	}
	
    @Override
    public void onReload() {
    	kvStoreProvider.onDependencyInjectionToContextCompleted();
    }
    
    /**
     * Injects kvstore to the Context.
     * @See SingletonTypeInjectableProvider
     * @author itaif
     */
    class KVStoreInjectableProvider implements InjectableProvider<Context, Type> , Injectable<KVStore> {

    	private KVStore kvstore;
    	
		@Override
		public ComponentScope getScope() {
			return ComponentScope.Singleton;
		}

		@Override
		public final Injectable<KVStore> getInjectable(ComponentContext ic, Context a, Type c) {
	        if (c.equals(KVStore.class)) {
	            return this;
	        } else
	            return null;
	    }

		@Override
		public KVStore getValue() {
			if (kvstore == null) {
				kvstore = new KVStore();
			}
			return kvstore;
		}

		public void onDependencyInjectionToContextCompleted() {
			kvstore = null;
			// next time getValue() is called, create a new kvstore
		}
    }
    
}
