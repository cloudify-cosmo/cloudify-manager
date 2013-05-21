package org.cloudifysource.cosmo.bootstrap;

import com.google.common.collect.ImmutableMap;

import java.util.Map;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class AgentBootstrapSetup extends BootstrapSetup {

    private static final String COSMO_URL = "COSMO_URL";
    private static final String COSMO_WORK_DIRECTORY = "COSMO_WORK_DIRECTORY";

    private final String cosmoUrl;

    public AgentBootstrapSetup(String scriptResourceLocation,
                               String workDirectory,
                               String propertiesResourceLocation,
                               String cosmoUrl) {
        super(scriptResourceLocation, workDirectory, propertiesResourceLocation);
        this.cosmoUrl = cosmoUrl;
    }

    @Override
    public Map<String, String> getScriptEnvironment() {
        return ImmutableMap.<String, String>builder()
                .put(COSMO_WORK_DIRECTORY, getWorkDirectory())
                .put(COSMO_URL, cosmoUrl)
                .build();
    }

}
