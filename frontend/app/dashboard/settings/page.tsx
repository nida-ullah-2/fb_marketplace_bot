"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { User, Lock, Save, Shield, LogOut } from "lucide-react";
import { authAPI } from "@/lib/api";
import { useToast, ToastContainer } from "@/components/ui/Toast";

type SettingsTab = "profile" | "security";

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");
  const [profileData, setProfileData] = useState({
    username: "",
    email: "",
    first_name: "",
    last_name: "",
  });
  const [passwordData, setPasswordData] = useState({
    old_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [loading, setLoading] = useState(false);
  const [profileLoading, setProfileLoading] = useState(true);
  const [currentPasswordError, setCurrentPasswordError] = useState(false);
  const { toasts, removeToast, success, error: showError } = useToast();

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("user");
    router.push("/login");
  };

  // Password validation helper
  const validatePassword = (password: string) => {
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    const hasSpecialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(
      password
    );
    const isLongEnough = password.length >= 8;

    return {
      hasUpperCase,
      hasLowerCase,
      hasNumber,
      hasSpecialChar,
      isLongEnough,
      isValid:
        hasUpperCase &&
        hasLowerCase &&
        hasNumber &&
        hasSpecialChar &&
        isLongEnough,
    };
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const response = await authAPI.getProfile();
      setProfileData({
        username: response.data.username || "",
        email: response.data.email || "",
        first_name: response.data.first_name || "",
        last_name: response.data.last_name || "",
      });
    } catch (err) {
      showError("Failed to load profile");
      console.error(err);
    } finally {
      setProfileLoading(false);
    }
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await authAPI.updateProfile(profileData);
      success("Profile updated successfully!");

      // Update user data in localStorage
      const user = JSON.parse(localStorage.getItem("user") || "{}");
      localStorage.setItem(
        "user",
        JSON.stringify({
          ...user,
          ...profileData,
        })
      );
    } catch (err) {
      const error = err as { response?: { data?: { error?: string } } };
      showError(error.response?.data?.error || "Failed to update profile");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Clear previous errors
    setCurrentPasswordError(false);

    // Validation
    if (!passwordData.old_password) {
      showError("Please enter your current password");
      return;
    }
    if (!passwordData.new_password) {
      showError("Please enter a new password");
      return;
    }

    // Validate password strength
    const validation = validatePassword(passwordData.new_password);
    if (!validation.isValid) {
      showError("Password must meet all requirements");
      return;
    }

    if (passwordData.new_password !== passwordData.confirm_password) {
      showError("New passwords do not match");
      return;
    }

    setLoading(true);

    try {
      await authAPI.changePassword(
        passwordData.old_password,
        passwordData.new_password
      );
      success("Password changed successfully!");

      // Clear password fields
      setPasswordData({
        old_password: "",
        new_password: "",
        confirm_password: "",
      });
      setCurrentPasswordError(false);
    } catch (err) {
      const error = err as { response?: { data?: { error?: string } } };
      const errorMessage =
        error.response?.data?.error || "Failed to change password";

      // Check if error is about incorrect current password
      if (
        errorMessage.toLowerCase().includes("current password is incorrect") ||
        errorMessage.toLowerCase().includes("old password")
      ) {
        setCurrentPasswordError(true);
      }

      showError(errorMessage);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (profileLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">⚙️ Settings</h1>
        <p className="text-gray-600 mt-1">
          Manage your account settings and preferences
        </p>
      </div>

      {/* Sidebar Layout */}
      <div className="flex gap-6 min-h-[calc(100vh-200px)]">
        {/* Sidebar */}
        <div className="w-64 flex-shrink-0">
          <Card className="h-full flex flex-col">
            {/* Navigation Section */}
            <CardContent className="p-4 flex-1">
              <nav className="space-y-2">
                <button
                  onClick={() => setActiveTab("profile")}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                    activeTab === "profile"
                      ? "bg-blue-50 text-blue-700 font-semibold"
                      : "text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  <User className="h-5 w-5" />
                  <span>Profile Info</span>
                </button>
                <button
                  onClick={() => setActiveTab("security")}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                    activeTab === "security"
                      ? "bg-blue-50 text-blue-700 font-semibold"
                      : "text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  <Shield className="h-5 w-5" />
                  <span>Security</span>
                </button>
              </nav>
            </CardContent>

            {/* Account Section at Bottom */}
            <div className="border-t border-gray-200 p-4">
              <div className="mb-3">
                <div className="flex items-center gap-3 px-2 py-2">
                  <div className="h-10 w-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-semibold">
                    {profileData.username
                      ? profileData.username.charAt(0).toUpperCase()
                      : "U"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {profileData.first_name && profileData.last_name
                        ? `${profileData.first_name} ${profileData.last_name}`
                        : profileData.username}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {profileData.email}
                    </p>
                  </div>
                </div>
              </div>
              <Button
                onClick={handleLogout}
                variant="outline"
                className="w-full flex items-center justify-center gap-2 text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 hover:border-red-300"
              >
                <LogOut className="h-4 w-4" />
                <span>Logout</span>
              </Button>
            </div>
          </Card>
        </div>

        {/* Main Content */}
        <div className="flex-1">
          {activeTab === "profile" && (
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User className="h-5 w-5" />
                  Profile Information
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleProfileSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Username */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-900 mb-2">
                        Username
                      </label>
                      <input
                        type="text"
                        value={profileData.username}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            username: e.target.value,
                          })
                        }
                        className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        required
                      />
                    </div>

                    {/* Email */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-900 mb-2">
                        Email
                      </label>
                      <input
                        type="email"
                        value={profileData.email}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            email: e.target.value,
                          })
                        }
                        className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        required
                      />
                    </div>

                    {/* First Name */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-900 mb-2">
                        First Name
                      </label>
                      <input
                        type="text"
                        value={profileData.first_name}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            first_name: e.target.value,
                          })
                        }
                        className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>

                    {/* Last Name */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-900 mb-2">
                        Last Name
                      </label>
                      <input
                        type="text"
                        value={profileData.last_name}
                        onChange={(e) =>
                          setProfileData({
                            ...profileData,
                            last_name: e.target.value,
                          })
                        }
                        className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button type="submit" disabled={loading}>
                      <Save className="h-4 w-4 mr-2" />
                      {loading ? "Saving..." : "Save Changes"}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {activeTab === "security" && (
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lock className="h-5 w-5" />
                  Change Password
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handlePasswordSubmit} className="space-y-4">
                  {/* Current Password */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-900 mb-2">
                      Current Password
                    </label>
                    <input
                      type="password"
                      value={passwordData.old_password}
                      onChange={(e) => {
                        setPasswordData({
                          ...passwordData,
                          old_password: e.target.value,
                        });
                        // Clear error when user starts typing
                        if (currentPasswordError) {
                          setCurrentPasswordError(false);
                        }
                      }}
                      className={`w-full px-3 py-2 text-sm text-gray-900 border rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        currentPasswordError ||
                        (!passwordData.old_password &&
                          (passwordData.new_password ||
                            passwordData.confirm_password))
                          ? "border-red-500"
                          : "border-gray-400"
                      }`}
                      placeholder="Enter current password"
                    />
                    {!passwordData.old_password &&
                      (passwordData.new_password ||
                        passwordData.confirm_password) && (
                        <p className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                          ⚠️ Please enter your current password
                        </p>
                      )}
                    {currentPasswordError && passwordData.old_password && (
                      <p className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                        ⚠️ Current password is incorrect. Please try again.
                      </p>
                    )}
                  </div>

                  {/* New Password */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-900 mb-2">
                      New Password
                    </label>
                    <input
                      type="password"
                      value={passwordData.new_password}
                      onChange={(e) =>
                        setPasswordData({
                          ...passwordData,
                          new_password: e.target.value,
                        })
                      }
                      className={`w-full px-3 py-2 text-sm text-gray-900 border rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        passwordData.new_password &&
                        !validatePassword(passwordData.new_password).isValid
                          ? "border-red-500"
                          : "border-gray-400"
                      }`}
                      placeholder="Enter new password"
                    />
                    {passwordData.new_password &&
                      (() => {
                        const validation = validatePassword(
                          passwordData.new_password
                        );
                        if (!validation.isValid) {
                          return (
                            <div className="mt-2 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2 space-y-1">
                              <p className="font-semibold text-red-700 mb-2">
                                ⚠️ Password must contain:
                              </p>
                              <div className="space-y-1">
                                <p
                                  className={
                                    validation.isLongEnough
                                      ? "text-green-600"
                                      : "text-red-600"
                                  }
                                >
                                  {validation.isLongEnough ? "✓" : "✗"} At least
                                  8 characters
                                </p>
                                <p
                                  className={
                                    validation.hasUpperCase
                                      ? "text-green-600"
                                      : "text-red-600"
                                  }
                                >
                                  {validation.hasUpperCase ? "✓" : "✗"} One
                                  uppercase letter (A-Z)
                                </p>
                                <p
                                  className={
                                    validation.hasLowerCase
                                      ? "text-green-600"
                                      : "text-red-600"
                                  }
                                >
                                  {validation.hasLowerCase ? "✓" : "✗"} One
                                  lowercase letter (a-z)
                                </p>
                                <p
                                  className={
                                    validation.hasNumber
                                      ? "text-green-600"
                                      : "text-red-600"
                                  }
                                >
                                  {validation.hasNumber ? "✓" : "✗"} One number
                                  (0-9)
                                </p>
                                <p
                                  className={
                                    validation.hasSpecialChar
                                      ? "text-green-600"
                                      : "text-red-600"
                                  }
                                >
                                  {validation.hasSpecialChar ? "✓" : "✗"} One
                                  special character (!@#$%^&*...)
                                </p>
                              </div>
                            </div>
                          );
                        }
                      })()}
                  </div>

                  {/* Confirm New Password */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-900 mb-2">
                      Confirm New Password
                    </label>
                    <input
                      type="password"
                      value={passwordData.confirm_password}
                      onChange={(e) =>
                        setPasswordData({
                          ...passwordData,
                          confirm_password: e.target.value,
                        })
                      }
                      className={`w-full px-3 py-2 text-sm text-gray-900 border rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        passwordData.confirm_password &&
                        passwordData.new_password &&
                        passwordData.confirm_password !==
                          passwordData.new_password
                          ? "border-red-500"
                          : "border-gray-400"
                      }`}
                      placeholder="Confirm new password"
                    />
                    {passwordData.confirm_password &&
                      passwordData.new_password &&
                      passwordData.confirm_password !==
                        passwordData.new_password && (
                        <p className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                          ⚠️ Passwords do not match
                        </p>
                      )}
                  </div>

                  <div className="flex justify-end">
                    <Button type="submit" disabled={loading}>
                      <Lock className="h-4 w-4 mr-2" />
                      {loading ? "Changing..." : "Change Password"}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
