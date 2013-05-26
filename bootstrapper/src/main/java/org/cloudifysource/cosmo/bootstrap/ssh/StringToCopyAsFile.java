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

/**
 * Encapsulates a string that is to be copied to a remote host a file.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class StringToCopyAsFile {

    private final String parentRemotePath;
    private final String name;
    private final String content;

    public StringToCopyAsFile(String parentRemotePath, String name, String content) {
        this.parentRemotePath = parentRemotePath;
        this.name = name;
        this.content = content;
    }

    public String getParentRemotePath() {
        return parentRemotePath;
    }

    public String getName() {
        return name;
    }

    public String getContent() {
        return content;
    }

}
