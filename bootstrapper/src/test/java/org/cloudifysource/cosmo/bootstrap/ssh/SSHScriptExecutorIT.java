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
******************************************************************************/

package org.cloudifysource.cosmo.bootstrap.ssh;

import com.google.common.collect.Lists;
import com.google.common.collect.Queues;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.bootstrap.config.BaseConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
* Tests the {@link SSHScriptExecutor}.
*
* @author Dan Kilman
* @since 0.1
*/
@ContextConfiguration(classes = { SSHScriptExecutorIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class SSHScriptExecutorIT extends AbstractTestNGSpringContextTests  {

    /**
     */
    @Configuration
    static class Config extends BaseConfig { }

    @Inject
    private SSHScriptExecutor sshClient;

    @Value("${cosmo.bootstrap.work-dir}")
    private String workDir;


    @Test(groups = "ssh", timeOut = 10000)
    public void testScriptNormal() throws Exception {
        String script = "echo from testScriptNormal";
        ListenableFuture<?> future = uploadScriptAndExecute("test_script.sh", script);
        assertThat(future.get()).isNull();
    }

    @Test(groups = "ssh", expectedExceptions = ExecutionException.class, timeOut = 10000)
    public void testScriptWithError() throws Exception {
        String script = "exit -1";
        ListenableFuture<?> future = uploadScriptAndExecute("test_script.sh", script);
        future.get();
    }


    @Test(groups = "ssh", timeOut = 10000)
    public void testExitStatus() throws Exception {
        final BlockingQueue<Throwable> queue = Queues.newArrayBlockingQueue(1);
        final int exitStatus = 100;
        String command = "exit " + exitStatus;
        ListenableFuture<?> future = uploadScriptAndExecute("test_script.sh", command);
        Futures.addCallback(future, new FutureCallback<Object>() {
            @Override
            public void onSuccess(Object result) {
                queue.offer(new AssertionError("Unexpected result"));
            }
            @Override
            public void onFailure(Throwable t) {
                queue.offer(t);
            }
        });
        Throwable throwable = queue.poll(5, TimeUnit.SECONDS);
        assertThat(throwable).isInstanceOf(SSHExecutionException.class);
        int actualExitStatus = ((SSHExecutionException) throwable).getExitStatus();
        assertThat(actualExitStatus).isEqualTo(exitStatus);
    }

    @Test(groups = "ssh", timeOut = 10000)
    public void testLineConsumedListener() throws ExecutionException, InterruptedException {
        final String output = "What?";
        final BlockingQueue<String> queue = Queues.newArrayBlockingQueue(1);
        String command = "echo " + output;
        uploadScriptAndExecute("test_script.sh", command, new LineConsumedListener() {
            @Override
            public void onLineConsumed(SSHConnectionInfo connectionInfo, String line) {
                queue.offer(line);
            }
        }).get();
        String line = queue.poll(5, TimeUnit.SECONDS);
        assertThat(line).isEqualTo(output);
    }

    private ListenableFuture<?> uploadScriptAndExecute(String scriptName, String script) {
        return uploadScriptAndExecute(scriptName, script, null);
    }

    private ListenableFuture<?> uploadScriptAndExecute(String scriptName, String script,
                                                       LineConsumedListener listener) {
        StringToCopyAsFile stringToCopyAsFile = new StringToCopyAsFile(workDir, scriptName, script);
        return sshClient.executeScript(workDir, workDir + scriptName,
                Lists.newArrayList(stringToCopyAsFile), listener);
    }


}
