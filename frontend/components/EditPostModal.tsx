"use client";

import { useState, useEffect } from "react";
import { Button } from "./ui/Button";
import { X, Upload } from "lucide-react";
import { postsAPI, accountsAPI } from "@/lib/api";
import Image from "next/image";
import type { MarketplacePost } from "@/types";

interface EditPostModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  onToast?: (type: "success" | "error", message: string) => void;
  post: MarketplacePost | null;
}

interface FacebookAccount {
  id: number;
  email: string;
  session_exists: boolean;
}

export default function EditPostModal({
  isOpen,
  onClose,
  onSuccess,
  onToast,
  post,
}: EditPostModalProps) {
  const [accounts, setAccounts] = useState<FacebookAccount[]>([]);
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    price: "",
    account: 0,
    posted: false,
  });
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen && post) {
      // Set form data from post
      setFormData({
        title: post.title,
        description: post.description,
        price: String(post.price),
        account:
          typeof post.account === "object" ? post.account.id : post.account,
        posted: post.posted || false,
      });
      setImagePreview(post.image || "");
      setImage(null);
      fetchAccounts();
    }
  }, [isOpen, post]);

  const fetchAccounts = async () => {
    try {
      const response = await accountsAPI.list();
      setAccounts(response.data);
    } catch (err) {
      console.error("Failed to fetch accounts:", err);
    }
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setError("Image size must be less than 5MB");
        return;
      }

      // Validate file type
      if (!file.type.startsWith("image/")) {
        setError("Please select an image file");
        return;
      }

      setImage(file);
      setError("");

      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleInputChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >
  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]:
        type === "checkbox"
          ? (e.target as HTMLInputElement).checked
          : name === "account"
          ? parseInt(value)
          : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!post) return;

    // Validation
    if (!formData.title.trim()) {
      setError("Title is required");
      return;
    }
    if (!formData.description.trim()) {
      setError("Description is required");
      return;
    }
    if (!formData.price || parseFloat(formData.price) <= 0) {
      setError("Please enter a valid price");
      return;
    }
    if (!formData.account) {
      setError("Please select an account");
      return;
    }

    setLoading(true);

    try {
      const submitData = new FormData();
      submitData.append("title", formData.title);
      submitData.append("description", formData.description);
      submitData.append("price", formData.price);
      submitData.append("account", formData.account.toString());
      submitData.append("posted", formData.posted.toString());

      // Only append image if a new one is selected
      if (image) {
        submitData.append("image", image);
      }

      await postsAPI.update(post.id, submitData);

      // Show success message
      if (onToast) {
        onToast("success", "Post updated successfully!");
      }

      onSuccess();
      onClose();
    } catch (err) {
      const error = err as { response?: { data?: { error?: string } } };
      const errorMessage =
        error.response?.data?.error ||
        "Failed to update post. Please try again.";
      setError(errorMessage);

      if (onToast) {
        onToast("error", errorMessage);
      }
      console.error("Error updating post:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !post) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white z-10">
          <h2 className="text-2xl font-bold text-gray-900">
            Edit Post -{" "}
            {typeof post.account === "object"
              ? post.account.email
              : "Unknown Account"}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close modal"
          >
            <X size={24} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4">
            {/* Account Selection */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Facebook Account <span className="text-red-500">*</span>
              </label>
              <select
                name="account"
                value={formData.account}
                onChange={handleInputChange}
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                aria-label="Select Facebook account"
              >
                <option value="">Select an account</option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.email}
                    {account.session_exists ? " ✓" : " (No Session)"}
                  </option>
                ))}
              </select>
            </div>

            {/* Title */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleInputChange}
                placeholder="e.g., iPhone 13 Pro - 256GB"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                maxLength={255}
                required
              />
              <p className="mt-1 text-sm text-gray-500">
                {formData.title.length}/255 characters
              </p>
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Description <span className="text-red-500">*</span>
              </label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                placeholder="Describe your item in detail..."
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={4}
                required
              />
              <p className="mt-1 text-sm text-gray-500">
                {formData.description.length} characters
              </p>
            </div>

            {/* Price */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Price ($) <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                name="price"
                value={formData.price}
                onChange={handleInputChange}
                placeholder="0.00"
                step="0.01"
                min="0.01"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-400 rounded-lg placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>

            {/* Posted Status */}
            <div className="flex items-center">
              <input
                type="checkbox"
                name="posted"
                id="posted"
                checked={formData.posted}
                onChange={handleInputChange}
                className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-2 focus:ring-blue-500"
              />
              <label
                htmlFor="posted"
                className="ml-2 text-sm font-medium text-gray-900"
              >
                Mark as Posted
              </label>
            </div>

            {/* Image Upload */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Product Image
              </label>

              {/* Current Image Preview */}
              {imagePreview && (
                <div className="mb-3">
                  <p className="text-sm text-gray-600 mb-2">Current Image:</p>
                  <Image
                    src={imagePreview}
                    alt="Current image"
                    width={400}
                    height={300}
                    className="max-h-64 rounded-lg object-contain border border-gray-300"
                  />
                </div>
              )}

              {/* File Upload */}
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-500 transition-colors">
                {image ? (
                  <div className="space-y-4">
                    <p className="text-sm text-green-600 font-medium">
                      New image selected
                    </p>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setImage(null);
                        setImagePreview(post.image || "");
                      }}
                    >
                      Cancel Change
                    </Button>
                  </div>
                ) : (
                  <div>
                    <Upload className="mx-auto h-12 w-12 text-gray-400" />
                    <p className="mt-2 text-sm text-gray-600">
                      Click to upload a new image
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      PNG, JPG, GIF up to 5MB
                    </p>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageChange}
                      className="hidden"
                      id="image-upload-edit"
                      aria-label="Upload product image"
                    />
                    <label htmlFor="image-upload-edit">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-4"
                        onClick={() =>
                          document.getElementById("image-upload-edit")?.click()
                        }
                      >
                        Change Image
                      </Button>
                    </label>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex gap-3 mt-6 pt-6 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={loading}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading} className="flex-1">
              {loading ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
