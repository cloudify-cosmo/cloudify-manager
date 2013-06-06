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

package org.cloudifysource.cosmo.dsl.tree;

import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;

import java.util.Map;

/**
 * A Tree based data structure where each node can have any number of children.
 *
 * @param <T> The tree node type.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Tree<T> {

    private final Node<T> root;
    private final Map<T, Node<T>> nodes = Maps.newHashMap();

    public Tree(T rootValue) {
        this.root = new Node<>(Preconditions.checkNotNull(rootValue));
        nodes.put(rootValue, root);
    }

    public void addNode(T value) {
        nodes.put(value, new Node<>(value));
    }

    public void setParentChildRelationship(T parentValue, T childValue) {
        Node<T> parentNode = nodes.get(parentValue);
        Node<T> childNode = nodes.get(childValue);
        Preconditions.checkArgument(parentNode != null, "No node for parent value %s", parentValue);
        Preconditions.checkArgument(childNode != null, "No node for child value %s", childValue);
        parentNode.addChild(childNode);
        childNode.setParent(parentNode);
    }

    public void validateLegalTree() {
        // TODO DSL implement
    }

    public void traverseParentThenChildren(Visitor<T> visitor) {
        root.acceptParentThenChildren(visitor);
    }

}
