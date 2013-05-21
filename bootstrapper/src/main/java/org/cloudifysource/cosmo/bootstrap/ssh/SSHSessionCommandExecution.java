package org.cloudifysource.cosmo.bootstrap.ssh;

import net.schmizz.sshj.connection.channel.direct.Session;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class SSHSessionCommandExecution {

    private final Session.Command sessionCommand;

    public SSHSessionCommandExecution(Session.Command sessionCommand) {
        this.sessionCommand = sessionCommand;
    }

}
