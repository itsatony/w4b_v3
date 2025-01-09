// FilePath: server/hub/internal/errors/errors.go
package errors

import (
	"fmt"
	"net/http"
)

// ErrorType represents the type of error
type ErrorType string

const (
	// Error types
	ErrorTypeValidation  ErrorType = "validation"
	ErrorTypeDatabase    ErrorType = "database"
	ErrorTypeAuth        ErrorType = "authentication"
	ErrorTypeAuthorize   ErrorType = "authorization"
	ErrorTypeNotFound    ErrorType = "not_found"
	ErrorTypeRateLimit   ErrorType = "rate_limit"
	ErrorTypeInternal    ErrorType = "internal"
	ErrorTypeUnavailable ErrorType = "service_unavailable"
)

// APIError represents a structured API error
type APIError struct {
	Type      ErrorType `json:"type"`
	Message   string    `json:"message"`
	Code      int       `json:"code"`
	RequestID string    `json:"request_id,omitempty"`
	Details   any       `json:"details,omitempty"`
	err       error     // Internal error for logging
}

// Error implements the error interface
func (e *APIError) Error() string {
	if e.err != nil {
		return fmt.Sprintf("%s: %s (internal: %v)", e.Type, e.Message, e.err)
	}
	return fmt.Sprintf("%s: %s", e.Type, e.Message)
}

// WithRequestID adds a request ID to the error
func (e *APIError) WithRequestID(id string) *APIError {
	e.RequestID = id
	return e
}

// WithDetails adds additional details to the error
func (e *APIError) WithDetails(details any) *APIError {
	e.Details = details
	return e
}

// NewValidationError creates a new validation error
func NewValidationError(msg string, err error) *APIError {
	return &APIError{
		Type:    ErrorTypeValidation,
		Message: msg,
		Code:    http.StatusBadRequest,
		err:     err,
	}
}

// NewDatabaseError creates a new database error
func NewDatabaseError(msg string, err error) *APIError {
	return &APIError{
		Type:    ErrorTypeDatabase,
		Message: msg,
		Code:    http.StatusInternalServerError,
		err:     err,
	}
}

// NewAuthError creates a new authentication error
func NewAuthError(msg string, err error) *APIError {
	return &APIError{
		Type:    ErrorTypeAuth,
		Message: msg,
		Code:    http.StatusUnauthorized,
		err:     err,
	}
}

// NewAuthorizationError creates a new authorization error
func NewAuthorizationError(msg string, err error) *APIError {
	return &APIError{
		Type:    ErrorTypeAuthorize,
		Message: msg,
		Code:    http.StatusForbidden,
		err:     err,
	}
}

// NewNotFoundError creates a new not found error
func NewNotFoundError(msg string, err error) *APIError {
	return &APIError{
		Type:    ErrorTypeNotFound,
		Message: msg,
		Code:    http.StatusNotFound,
		err:     err,
	}
}

// NewRateLimitError creates a new rate limit error
func NewRateLimitError(msg string, err error) *APIError {
	return &APIError{
		Type:    ErrorTypeRateLimit,
		Message: msg,
		Code:    http.StatusTooManyRequests,
		err:     err,
	}
}

// NewInternalError creates a new internal server error
func NewInternalError(msg string, err error) *APIError {
	return &APIError{
		Type:    ErrorTypeInternal,
		Message: msg,
		Code:    http.StatusInternalServerError,
		err:     err,
	}
}

// IsNotFound checks if an error is a NotFound error
func IsNotFound(err error) bool {
	if apiErr, ok := err.(*APIError); ok {
		return apiErr.Type == ErrorTypeNotFound
	}
	return false
}

// IsValidation checks if an error is a Validation error
func IsValidation(err error) bool {
	if apiErr, ok := err.(*APIError); ok {
		return apiErr.Type == ErrorTypeValidation
	}
	return false
}
