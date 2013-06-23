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

package org.cloudifysource.cosmo.dsl.packaging;

import java.nio.file.Path;

/**
 * The outcome of a {@link DSLPackageProcessor#process(java.io.File, java.io.File)} invocation which contains the
 * main DSL of the package and a string pointing to the package's root directory.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class ExtractedDSLPackageDetails {

    private final Path dslPath;
    private final String packageLocation;

    public ExtractedDSLPackageDetails(Path dslPath, String packageLocation) {
        this.dslPath = dslPath;
        this.packageLocation = packageLocation;
    }

    public Path getDslPath() {
        return dslPath;
    }

    public String getPackageLocation() {
        return packageLocation;
    }
}
