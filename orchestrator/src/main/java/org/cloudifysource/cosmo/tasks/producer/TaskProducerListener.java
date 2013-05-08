package org.cloudifysource.cosmo.tasks.producer;

import org.cloudifysource.cosmo.tasks.messages.TaskMessage;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public interface TaskProducerListener {

    void onTaskUpdateReceived(TaskMessage result);
    void onFailure(Throwable t);

}
