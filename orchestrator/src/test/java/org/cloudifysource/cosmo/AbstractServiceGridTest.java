package org.cloudifysource.cosmo;

import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.mock.MockAgent;
import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.mock.MockTaskContainer;
import org.cloudifysource.cosmo.mock.MockTaskContainerParameter;
import org.cloudifysource.cosmo.mock.TaskConsumerRegistrar;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.cloudifysource.cosmo.time.MockCurrentTimeProvider;
import org.junit.AfterClass;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.log.TextFormatter;

import java.lang.reflect.Method;
import java.net.URI;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

public abstract class AbstractServiceGridTest<T extends MockManagement> {

    private final Logger logger;
    private T management;
    private Set<MockTaskContainer> containers;
    private MockCurrentTimeProvider timeProvider;
    private long startTimestamp;
    private TaskConsumerRegistrar taskConsumerRegistrar;

    public AbstractServiceGridTest() {
        logger = Logger.getLogger(this.getClass().getName());
        setSimpleLoggerFormatter(logger);
    }

    @BeforeClass
    public void beforeClass() {

        containers =  Sets.newSetFromMap(new ConcurrentHashMap<MockTaskContainer, Boolean>());
        timeProvider = new MockCurrentTimeProvider(startTimestamp);
        taskConsumerRegistrar = new TaskConsumerRegistrar() {

            @Override
            public void registerTaskConsumer(
                    final Object taskConsumer, final URI taskConsumerId) {

                MockTaskContainer container = newContainer(taskConsumerId, taskConsumer);
                addContainer(container);
            }

            @Override
            public Object unregisterTaskConsumer(final URI taskConsumerId) {
                MockTaskContainer mockTaskContainer = findContainer(taskConsumerId);
                boolean removed = containers.remove(mockTaskContainer);
                Preconditions.checkState(removed, "Failed to remove container " + taskConsumerId);
                return mockTaskContainer.getTaskConsumer();
            }
        };

        management = createMockManagement();
        management.setTaskConsumerRegistrar(taskConsumerRegistrar);
        management.setTimeProvider(timeProvider);
    }

    protected abstract T createMockManagement();

    @BeforeMethod
    public void beforeMethod(Method method) {

        startTimestamp = System.currentTimeMillis();
        timeProvider.setCurrentTimeMillis(startTimestamp);
        management.start();
        logger.info("Starting " + method.getName());
    }

    @AfterMethod(alwaysRun=true)
    public void afterMethod(Method method) {

        try {
            management.unregisterTaskConsumers();
            final Function<MockTaskContainer, URI> getContainerIdFunc = new Function<MockTaskContainer, URI>() {

                @Override
                public URI apply(MockTaskContainer input) {
                    return input.getTaskConsumerId();
                }
            };

            Assert.assertEquals(containers.size(), 0, "Cleanup failure in test " + method.getName() + ":"+ Iterables
                    .toString(Iterables.transform(containers, getContainerIdFunc)));

        }
        finally {
            containers.clear();
        }
    }

    @AfterClass
    public void afterClass() {
        management.close();
    }

    private static void setSimpleLoggerFormatter(final Logger logger) {
        Logger parentLogger = logger;
        while (parentLogger.getHandlers().length == 0) {
            parentLogger = logger.getParent();
        }

        parentLogger.getHandlers()[0].setFormatter(new TextFormatter());
    }

    private void addContainer(MockTaskContainer container) {
        //logger.info("Adding container for " + container.getExecutorId());
        Preconditions.checkState(findContainserById(container.getTaskConsumerId()) == null, "Container " + container.getTaskConsumerId() + " was already added");
        containers.add(container);
    }

    private MockTaskContainer findContainserById(final URI id) {
        return Iterables.find(containers, new Predicate<MockTaskContainer>(){

            @Override
            public boolean apply(MockTaskContainer container) {
                return id.equals(container.getTaskConsumerId());
            }}, null);
    }

    private MockTaskContainer newContainer(
            URI executorId,
            Object taskConsumer) {
        MockTaskContainerParameter containerParameter = new MockTaskContainerParameter();
        containerParameter.setExecutorId(executorId);
        containerParameter.setTaskConsumer(taskConsumer);
        containerParameter.setStateReader(management.getStateReader());
        containerParameter.setStateWriter(management.getStateWriter());
        containerParameter.setTaskReader(management.getTaskReader());
        containerParameter.setTaskWriter(management.getTaskWriter());
        containerParameter.setPersistentTaskReader(management.getPersistentTaskReader());
        containerParameter.setPersistentTaskWriter(management.getPersistentTaskWriter());
        containerParameter.setTimeProvider(timeProvider);
        return new MockTaskContainer(containerParameter);
    }

    protected MockTaskContainer findContainer(final URI agentId) {
        MockTaskContainer container = Iterables.tryFind(containers, new Predicate<MockTaskContainer>() {

            @Override
            public boolean apply(MockTaskContainer container) {
                return agentId.equals(container.getTaskConsumerId());
            }
        }).orNull();

        Preconditions.checkNotNull(container, "Cannot find container for %s", agentId);
        return container;
    }

    protected T getManagement() {
        return this.management;
    }
    protected void execute(URI ... taskProducers) {

        int consecutiveEmptyCycles = 0;
        for (; timeProvider.currentTimeMillis() < startTimestamp + 1000000; timeProvider.increaseBy(1000 - (timeProvider.currentTimeMillis() % 1000))) {

            boolean emptyCycle = true;

            for (final URI taskProducer : taskProducers) {
                submitTaskProducerTask(taskProducer);
                timeProvider.increaseBy(1);
            }

            for (MockTaskContainer container : containers) {
                Preconditions.checkState(containers.contains(container));
                Assert.assertEquals(container.getTaskConsumerId().getHost(),"localhost");
                Task task = null;

                for(; (task = container.consumeNextTask()) != null; timeProvider.increaseBy(1)) {
                    if (!(task instanceof TaskProducerTask) && !(task instanceof PingAgentTask)) {
                        emptyCycle = false;
                    }
                }
            }

            if (emptyCycle) {
                consecutiveEmptyCycles++;
            }
            else {
                consecutiveEmptyCycles = 0;
            }

            if (consecutiveEmptyCycles > 60) {
                return;
            }
        }

        Assert.fail("Executing too many cycles progress.");
    }

    private void submitTaskProducerTask(final URI taskProducerId) {
        final TaskProducerTask producerTask = new TaskProducerTask();
        producerTask.setMaxNumberOfSteps(100);
        submitTask(taskProducerId, producerTask);
    }

    protected void submitTask(final URI target, final Task task) {
        task.setProducerTimestamp(timeProvider.currentTimeMillis());
        task.setProducerId(StreamUtils.newURI(getManagement().getStateServerUri() + "webui"));
        task.setConsumerId(target);
        getManagement().getTaskWriter().postNewTask(task);
    }

    protected long currentTimeMillis() {
        return timeProvider.currentTimeMillis();
    }

    /**
     * This method simulates failure of the agent, and immediate restart by a reliable watchdog
     * running on the same machine
     */
    protected void restartAgent(URI agentId) {

        MockAgent agent = (MockAgent) taskConsumerRegistrar.unregisterTaskConsumer(agentId);
        AgentState agentState = agent.getState();
        Preconditions.checkState(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
        agentState.setNumberOfAgentRestarts(agentState.getNumberOfAgentRestarts() +1);
        taskConsumerRegistrar.registerTaskConsumer(new MockAgent(agentState), agentId);
    }


    /**
     * This method simulates an unexpected crash of a machine
     */
    protected void killMachine(URI agentId) {
        findContainer(agentId).killMachine();
    }
}
