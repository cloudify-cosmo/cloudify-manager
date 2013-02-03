package org.openspaces.servicegrid.state;

import com.google.common.hash.HashCode;
import com.google.common.hash.Hashing;

public class Etag {

	public static Etag EMPTY = create("EMPTY");
	
	final HashCode hash;
	
	protected Etag(HashCode hash) {
		this.hash = hash;
	}

	public static Etag create(String input) {
		return new Etag(Hashing.md5().hashString(input));
	}
	
	@Override
	public int hashCode() {
		return hash.hashCode();
	}

	@Override
	public boolean equals(Object obj) {
		if (obj instanceof Etag) {
			Etag etag = (Etag) obj;
			return hash.equals(etag.hash);	
		}
		return false;
	}

	@Override
	public String toString() {
		return hash.toString();
	}

}
