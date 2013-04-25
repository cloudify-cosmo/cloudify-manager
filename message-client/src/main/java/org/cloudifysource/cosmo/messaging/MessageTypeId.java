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
package org.cloudifysource.cosmo.messaging;

import com.google.common.base.CaseFormat;

/**
 * Converts class names into message id string.
 *
 * @author itaif
 * @since 0.1
 */
public class MessageTypeId {

    private MessageTypeId() { }

    public static String toMessageTypeId(Class<?> clazz) {
        return CaseFormat.UPPER_CAMEL.to(CaseFormat.LOWER_UNDERSCORE, clazz.getSimpleName());
    }
}
