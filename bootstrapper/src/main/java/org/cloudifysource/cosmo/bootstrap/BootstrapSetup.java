package org.cloudifysource.cosmo.bootstrap;

import java.util.Map;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public abstract class BootstrapSetup {

    private final String scriptResourceLocation;
    private final String workDirectory;
    private final String propertiesResourceLocation;

    public BootstrapSetup(String scriptResourceLocation, String workDirectory,
                          String propertiesResourceLocation) {
        this.scriptResourceLocation = scriptResourceLocation;
        this.workDirectory = workDirectory;
        this.propertiesResourceLocation = propertiesResourceLocation;
    }

    /* This has to be outside so we know where to copy files. the rest should reside in env or properties. */
    public String getWorkDirectory() {
        return workDirectory;
    }

    public String getScriptResourceLocation() {
        return scriptResourceLocation;
    }

    public abstract Map<String, String> getScriptEnvironment();

    public String getPropertiesResourceLocation() {
        return propertiesResourceLocation;
    }

}
