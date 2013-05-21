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
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests the {@link SSHClient}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@ContextConfiguration(classes = { SSHClientIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class SSHClientIT extends AbstractTestNGSpringContextTests  {

    /**
     */
    @Configuration
    static class Config extends BaseConfig { }

    @Inject
    private SSHClient sshClient;

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
    public void testConcurrentCommands() throws Exception {
        final CountDownLatch latch = new CountDownLatch(3);
        final AtomicReference<Long> future1EndTimestamp = new AtomicReference<>();
        final AtomicReference<Long> future2EndTimestamp = new AtomicReference<>();
        final AtomicReference<Long> future3EndTimestamp = new AtomicReference<>();
        ListenableFuture<?> future1 = uploadScriptAndExecute("test_script1.sh", "sleep 3");
        Thread.sleep(100);
        ListenableFuture<?> future2 = uploadScriptAndExecute("test_script2.sh", "sleep 2");
        Thread.sleep(100);
        ListenableFuture<?> future3 = uploadScriptAndExecute("test_script3.sh", "sleep 1");
        Futures.addCallback(future1, new FutureCallback<Object>() {
            public void onSuccess(Object result) {
                future1EndTimestamp.set(System.currentTimeMillis());
                latch.countDown();
            }
            public void onFailure(Throwable t) { }
        });
        Futures.addCallback(future2, new FutureCallback<Object>() {
            public void onSuccess(Object result) {
                future2EndTimestamp.set(System.currentTimeMillis());
                latch.countDown();
            }
            public void onFailure(Throwable t) { }
        });
        Futures.addCallback(future3, new FutureCallback<Object>() {
            public void onSuccess(Object result) {
                future3EndTimestamp.set(System.currentTimeMillis());
                latch.countDown();
            }
            public void onFailure(Throwable t) { }
        });
        latch.await();
        assertThat(future1EndTimestamp.get()).isGreaterThan(future2EndTimestamp.get());
        assertThat(future2EndTimestamp.get()).isGreaterThan(future3EndTimestamp.get());
    }

    @Test(groups = "ssh", timeOut = 10000)
    public void testExecute() throws Exception {
        final CountDownLatch latch = new CountDownLatch(1);
        final AtomicBoolean validOutcome = new AtomicBoolean(false);
        final int exitStatus = 100;
        String command = "exit " + exitStatus;
        ListenableFuture<?> future = sshClient.execute(command);
        Futures.addCallback(future, new FutureCallback<Object>() {
            @Override
            public void onSuccess(Object result) {
                latch.countDown();
            }
            @Override
            public void onFailure(Throwable t) {
                validOutcome.set(t instanceof SSHExecutionException &&
                                ((SSHExecutionException) t).getExitStatus() == exitStatus);
                latch.countDown();
            }
        });
        latch.await();
        assertThat(validOutcome.get()).isTrue();
    }

    @Test(groups = "ssh", timeOut = 10000)
    public void testLineConsumedListener() throws ExecutionException, InterruptedException {
        final String output = "What?";
        final AtomicBoolean validOutput = new AtomicBoolean(false);
        final CountDownLatch outputLatch = new CountDownLatch(1);
        String command = "echo " + output;
        sshClient.execute(command, new LineConsumedListener() {
            @Override
            public void onLineConsumed(SSHConnectionInfo connectionInfo, String line) {
                validOutput.set(line.equals(output));
                outputLatch.countDown();
            }
        }).get();
        outputLatch.await();
        assertThat(validOutput.get()).isTrue();
    }

    private ListenableFuture<?> uploadScriptAndExecute(String scriptName, String script) {
        sshClient.putString(workDir, scriptName, script);
        return sshClient.executeScript(workDir, workDir + scriptName);
    }



}
