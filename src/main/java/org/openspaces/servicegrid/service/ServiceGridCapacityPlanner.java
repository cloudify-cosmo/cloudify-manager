package org.openspaces.servicegrid.service;

import java.net.URI;
import java.util.List;
import java.util.Map.Entry;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskProducer;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridCapacityPlannerState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceScalingRule;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.ScaleServiceTask;
import org.openspaces.servicegrid.service.tasks.ScalingRulesTask;
import org.openspaces.servicegrid.streams.StreamReader;

import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;

public class ServiceGridCapacityPlanner {

	private final ServiceGridCapacityPlannerState state;
	private final StreamReader<Task> taskReader;
	private final URI deploymentPlannerId;
	private final StreamReader<TaskConsumerState> stateReader;

	public ServiceGridCapacityPlanner(ServiceGridCapacityPlannerParameter parameterObject) {
		this.deploymentPlannerId = parameterObject.getDeploymentPlannerId();
		this.stateReader = parameterObject.getStateReader();
		this.taskReader = parameterObject.getTaskReader();
		this.state = new ServiceGridCapacityPlannerState();
	}
	
	@TaskConsumerStateHolder
	public ServiceGridCapacityPlannerState getState() {
		return this.state;
	}
	
	@TaskConsumer
	public void scalingRules(ScalingRulesTask task) {
		state.addServiceScalingRule(task.getServiceId(), task.getScalingRule());
	}
	
	@TaskProducer
	public Iterable<Task> enforceScalingRules() {
		
		final List<Task> newTasks = Lists.newArrayList();
		
		for (Entry<URI, ServiceScalingRule>  entry : state.getScalingRuleByService().entrySet()) {
			final URI serviceId = entry.getKey();
			final ServiceScalingRule scalingRule = entry.getValue();
			enforceScalingRule(newTasks, serviceId, scalingRule);
		}
		
		return newTasks;
	}

	private void enforceScalingRule(List<Task> newTasks, URI serviceId, ServiceScalingRule scalingRule) {
		
		ServiceState serviceState = getServiceState(serviceId);
		if (shouldScaleOut(scalingRule, serviceState)) {
		
			final int plannedNumberOfInstances = serviceState.getInstanceIds().size() + 1;
			scale(newTasks, serviceState.getServiceConfig(), plannedNumberOfInstances);
		}
		else if (shouldScaleIn(scalingRule, serviceState)) {
			
			final int plannedNumberOfInstances = serviceState.getInstanceIds().size() - 1;
			scale(newTasks, serviceState.getServiceConfig(), plannedNumberOfInstances);
		}
	}

	private void scale(List<Task> newTasks, 
			ServiceConfig serviceConfig, final int plannedNumberOfInstances) {
		
		if (plannedNumberOfInstances >= serviceConfig.getMinNumberOfInstances() &&
			plannedNumberOfInstances <= serviceConfig.getMaxNumberOfInstances()) {
			
			final ScaleServiceTask task = new ScaleServiceTask();
			task.setServiceId(serviceConfig.getServiceId());
			task.setPlannedNumberOfInstances(plannedNumberOfInstances);
			task.setTarget(deploymentPlannerId);
			addNewTaskIfNotExists(newTasks, task);
		}
	}
	
	/**
	 * Scale out if any of the instances property value is above threshold
	 */
	private boolean shouldScaleOut(
			final ServiceScalingRule scalingRule,
			final ServiceState serviceState) {
		
		boolean scaleOut = false;
		
		if (isServiceInstalled(serviceState)) {
				
			Object highThreshold = scalingRule.getHighThreshold();
			if (highThreshold != null) {
				for (URI instanceId : serviceState.getInstanceIds()) {
					final Object value = getServiceInstanceState(instanceId).getProperty(scalingRule.getPropertyName());
					if (value != null && isAboveThreshold(highThreshold, value)) {
						scaleOut = true;
						break;
					}
				}
			}
		}
		return scaleOut;
	}

	/**
	 * Scale in if all instances property value is below threshold.
	 */
	private boolean shouldScaleIn(
			final ServiceScalingRule scalingRule,
			final ServiceState serviceState) {
		
		boolean scaleIn = false;
		
		if (isServiceInstalled(serviceState)) {
			Object lowThreshold = scalingRule.getLowThreshold();
			if (lowThreshold != null) {
				scaleIn = true;
				for (URI instanceId : serviceState.getInstanceIds()) {
					final Object value = getServiceInstanceState(instanceId).getProperty(scalingRule.getPropertyName());
					if (value == null) {
						scaleIn = false;
						break;
					}
					else if (!isBelowThreshold(lowThreshold, value)) {
						scaleIn = false;
						break;
					}
				}
			}
		}
		return scaleIn;
	}
	
	private boolean isServiceInstalled(final ServiceState serviceState) {
		return serviceState != null &&
			serviceState.getProgress().equals(ServiceState.Progress.SERVICE_INSTALLED);
	}
	
	private boolean isAboveThreshold(Object threshold, Object value) {
		return compare(threshold, value) < 0;
	}
	
	private boolean isBelowThreshold(Object threshold, Object value) {
		return compare(threshold, value) > 0;
	}

	private ServiceState getServiceState(final URI serviceId) {
		return ServiceUtils.getServiceState(stateReader, serviceId);
	}
	
	private ServiceInstanceState getServiceInstanceState(URI instanceId) {
		return ServiceUtils.getServiceInstanceState(stateReader, instanceId);
	}
	
	/**
	 * Adds a new task only if it has not been added recently.
	 */
	public void addNewTaskIfNotExists(
			final List<Task> newTasks,
			final Task newTask) {
		
		if (ServiceUtils.getExistingTaskId(stateReader, taskReader, newTask) == null) {
			addNewTask(newTasks, newTask);
		}
	}
	

	private static void addNewTask(List<Task> newTasks, final Task task) {
		newTasks.add(task);
	}

    @SuppressWarnings("unchecked")
	public static int compare(Object left, Object right) throws NumberFormatException {

    	Preconditions.checkNotNull(left);
    	Preconditions.checkNotNull(right);
    	
        if (left.getClass().equals(right.getClass()) && 
        	left instanceof Comparable<?>) {
            return ((Comparable<Object>) left).compareTo(right);
        }

        return toDouble(left).compareTo(toDouble(right));
    }
	
	private static Double toDouble(Object x) throws NumberFormatException {
        if (x instanceof Number) {
            return ((Number) x).doubleValue();
        }
        return Double.valueOf(x.toString());
    }
}
