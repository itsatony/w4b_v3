package middleware

import (
	"context"
	"net/http"
	"strings"

	"github.com/Nerzal/gocloak/v13"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
)

type KeycloakConfig struct {
	URL          string
	Realm        string
	ClientID     string
	ClientSecret string
}

type KeycloakMiddleware struct {
	client       *gocloak.GoCloak
	config       KeycloakConfig
	publicClient *gocloak.GoCloak
}

type UserContext struct {
	ID       string   `json:"id"`
	Username string   `json:"username"`
	Email    string   `json:"email"`
	Roles    []string `json:"roles"`
}

func NewKeycloakMiddleware(config KeycloakConfig) *KeycloakMiddleware {
	return &KeycloakMiddleware{
		client:       gocloak.NewClient(config.URL),
		publicClient: gocloak.NewClient(config.URL),
		config:       config,
	}
}

// Authenticate validates the token and adds user info to context
func (k *KeycloakMiddleware) Authenticate(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		token := extractToken(r)
		if token == "" {
			handleError(w, errors.NewAuthError("no token provided", nil))
			return
		}

		// Verify token
		result, err := k.client.RetrospectToken(r.Context(), token, k.config.ClientID, k.config.ClientSecret, k.config.Realm)
		if err != nil || !*result.Active {
			handleError(w, errors.NewAuthError("invalid token", err))
			return
		}

		roles, err := k.client.GetRealmRoles(r.Context(), token, k.config.Realm, gocloak.GetRoleParams{})
		if err != nil {
			handleError(w, errors.NewAuthError("failed to get realm roles", err))
			return
		}
		// Decode token
		claims, err := k.client.GetUserInfo(r.Context(), token, k.config.Realm)
		if err != nil {
			handleError(w, errors.NewAuthError("failed to get user info", err))
			return
		}

		// Extract user info and roles
		userContext, err := k.createUserContext(claims, roles)
		if err != nil {
			handleError(w, errors.NewAuthError("failed to create user context", err))
			return
		}

		// Add user context to request context
		type contextKey string
		ctx := context.WithValue(r.Context(), contextKey("user"), userContext)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// RequireRoles middleware ensures user has required roles
func (k *KeycloakMiddleware) RequireRoles(roles []string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			user, ok := r.Context().Value("user").(*UserContext)
			if !ok {
				handleError(w, errors.NewAuthError("no user context found", nil))
				return
			}

			if !hasRequiredRoles(user.Roles, roles) {
				handleError(w, errors.NewAuthorizationError("insufficient permissions", nil))
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// Helper functions

func (k *KeycloakMiddleware) createUserContext(userInfo *gocloak.UserInfo, roles []*gocloak.Role) (*UserContext, error) {
	userContext := &UserContext{
		ID:       *userInfo.Sub,
		Username: *userInfo.PreferredUsername,
		Email:    *userInfo.Email,
		Roles:    extractRoles(roles),
	}
	return userContext, nil
}

func extractToken(r *http.Request) string {
	bearerToken := r.Header.Get("Authorization")
	if len(strings.Split(bearerToken, " ")) == 2 {
		return strings.Split(bearerToken, " ")[1]
	}
	return ""
}

func extractRoles(roles []*gocloak.Role) []string {
	var roleStrings []string
	for _, role := range roles {
		roleStrings = append(roleStrings, *role.Name)
	}
	return roleStrings
}

func hasRequiredRoles(userRoles, requiredRoles []string) bool {
	if len(requiredRoles) == 0 {
		return true
	}

	roleMap := make(map[string]bool)
	for _, role := range userRoles {
		roleMap[role] = true
	}

	for _, required := range requiredRoles {
		if required == "*" {
			return true
		}
		if !roleMap[required] {
			return false
		}
	}
	return true
}

func handleError(w http.ResponseWriter, err error) {
	if apiErr, ok := err.(*errors.APIError); ok {
		http.Error(w, apiErr.Message, apiErr.Code)
		return
	}
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}
