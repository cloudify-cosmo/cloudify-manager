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

package org.cloudifysource.cosmo.manager;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;

import java.io.File;
import java.io.FileOutputStream;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class DSLPackage {

    private final List<FileEntry> entries;

    private DSLPackage(List<FileEntry> entries) {
        Preconditions.checkNotNull(entries);
        this.entries = entries;
    }

    public void write(File file) {
        Preconditions.checkArgument(!file.exists(), "File already exists");
        ZipOutputStream zipOutputStream = null;
        try {
            zipOutputStream = new ZipOutputStream(new FileOutputStream(file));
            for (FileEntry entry : entries) {
                zipOutputStream.putNextEntry(new ZipEntry(entry.getFilePath()));
                zipOutputStream.write(entry.getContent());
            }
        } catch (Exception e) {
            throw Throwables.propagate(e);
        } finally {
            try {
                if (zipOutputStream != null) {
                    zipOutputStream.flush();
                    zipOutputStream.close();
                }
            } catch (Exception ignored) {
            }
        }
    }

    /**
     * @author Idan Moyal
     * @since 0.1
     */
    public static class DSLPackageBuilder {

        private final List<FileEntry> entries = Lists.newLinkedList();

        public DSLPackageBuilder addFile(String filePath, byte[] content) {
            entries.add(new FileEntry(filePath, content));
            return this;
        }

        public DSLPackageBuilder addFile(String filePath, String content) {
            entries.add(new FileEntry(filePath, content.getBytes()));
            return this;
        }

        public DSLPackage build() {
            return new DSLPackage(entries);
        }
    }

    /**
     *
     */
    private static class FileEntry {

        private final String filePath;
        private final byte[] content;

        public FileEntry(String filePath, byte[] content) {
            this.filePath = filePath;
            this.content = content;
        }

        public String getFilePath() {
            return filePath;
        }

        public byte[] getContent() {
            return content;
        }
    }

}
