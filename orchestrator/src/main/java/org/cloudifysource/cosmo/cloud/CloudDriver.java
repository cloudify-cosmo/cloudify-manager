/*
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *       http://www.apache.org/licenses/LICENSE-2.0
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.cloudifysource.cosmo.cloud;

import com.google.common.base.Optional;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import org.jclouds.ContextBuilder;
import org.jclouds.compute.ComputeServiceContext;
import org.jclouds.compute.RunNodesException;
import org.jclouds.compute.domain.ComputeMetadata;
import org.jclouds.compute.domain.NodeMetadata;
import org.jclouds.compute.domain.OsFamily;
import org.jclouds.compute.domain.Template;
import org.jclouds.ec2.domain.InstanceType;

import java.util.Set;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Niv Ingberg
 * @since 0.1
 */
public class CloudDriver {
    private final ComputeServiceContext context;
    private Template defaultTemplate;

    public static CloudDriver createEC2(String accessKeyId, String secretKey) {
        ContextBuilder builder = ContextBuilder.newBuilder("aws-ec2")
                .credentials(accessKeyId, secretKey);
        final ComputeServiceContext context = builder.build(ComputeServiceContext.class);
        return new CloudDriver(context);
    }

    public CloudDriver(ComputeServiceContext context) {
        this.context = context;
    }

    public void close() {
        context.close();
    }

    public NodeMetadata create(String name) throws RunNodesException {
        final Set<? extends NodeMetadata> nodes =
                context.getComputeService().createNodesInGroup(name, 1, getDefaultTemplate());
        return Iterables.getOnlyElement(nodes);
    }

    public void suspend(NodeMetadata node) {
        context.getComputeService().suspendNode(node.getId());
    }

    public void resume(NodeMetadata node) {
        context.getComputeService().resumeNode(node.getId());
    }

    public void destroy(NodeMetadata node) {
        context.getComputeService().destroyNode(node.getId());
    }

    public Set<? extends NodeMetadata> searchNodes(Predicate<ComputeMetadata> filter) {
        return context.getComputeService().listNodesDetailsMatching(filter);
    }

    public Optional<NodeMetadata> searchSingleNode(Predicate<ComputeMetadata> filter) {
        final Set<? extends NodeMetadata> nodes = searchNodes(filter);
        if (nodes.isEmpty())
            return Optional.absent();
        return Optional.of(Iterables.getOnlyElement(nodes));
    }

    public Optional<NodeMetadata> searchNodeById(String id) {
        return searchSingleNode(org.jclouds.compute.predicates.NodePredicates.withIds(id));
    }

    private Template getDefaultTemplate() {
        if (defaultTemplate == null) {
            defaultTemplate = context.getComputeService().templateBuilder()
                    .hardwareId(InstanceType.T1_MICRO)
                    .osFamily(OsFamily.AMZN_LINUX)
                    .build();
        }
        return defaultTemplate;
    }
}
