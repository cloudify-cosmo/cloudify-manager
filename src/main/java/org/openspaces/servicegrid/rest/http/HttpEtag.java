package org.openspaces.servicegrid.rest.http;

public class HttpEtag {

	public final static HttpEtag NOT_EXISTS = new HttpEtag("NOT_EXISTS");
	
	private final String etag;
	
	public HttpEtag(String etag) {
		this.etag = etag;
	}

	@Override
	public int hashCode() {
		final int prime = 31;
		int result = 1;
		result = prime * result + ((etag == null) ? 0 : etag.hashCode());
		return result;
	}

	@Override
	public boolean equals(Object obj) {
		if (this == obj)
			return true;
		if (obj == null)
			return false;
		if (getClass() != obj.getClass())
			return false;
		HttpEtag other = (HttpEtag) obj;
		if (etag == null) {
			if (other.etag != null)
				return false;
		} else if (!etag.equals(other.etag))
			return false;
		return true;
	}

	
}
