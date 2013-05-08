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
 *******************************************************************************/

package org.cloudifysource.cosmo.cep.config;

import javax.validation.Constraint;
import javax.validation.ConstraintValidator;
import javax.validation.ConstraintValidatorContext;
import javax.validation.Payload;
import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import java.net.URI;


/**
 * A topic URI constraint.
 *
 * TODO refactor this class (extract validator and error message) and move it to message client (probably to consumer)
 *
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Target({ ElementType.FIELD })
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = Topic.TopicValidator.class)
@Documented
public @interface Topic {

    String message() default "Due to a known issue the topic URI cannot contain underscores.";

    /**
     * @see:
     * http://docs.jboss.org/hibernate/validator/5.0/reference/en-US/html_single/#validator-customconstraints-simple
     * for a detailed description of custom constraints.
     * Generally the validator will be moved to its own file and the default message
     * will be interpolated from ValidationMessages.properties.
     */
    static class TopicValidator implements ConstraintValidator<Topic, URI> {
        @Override
        public void initialize(Topic constraintAnnotation) {
        }
        @Override
        public boolean isValid(URI value, ConstraintValidatorContext context) {
            return value == null || !value.getPath().contains("_");
        }
    }

    Class<?>[] groups() default { };
    Class<? extends Payload>[] payload() default { };
}
