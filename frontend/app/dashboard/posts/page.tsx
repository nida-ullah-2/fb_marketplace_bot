"use client";

import { useEffect, useState, useRef } from "react";
import { postsAPI } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import {
  Package,
  CheckCircle,
  XCircle,
  Trash2,
  Plus,
  Edit,
  Image as ImageIcon,
} from "lucide-react";
import Image from "next/image";
import CreatePostModal from "@/components/CreatePostModal";
import EditPostModal from "@/components/EditPostModal";
import BulkUploadPostsModal from "@/components/BulkUploadPostsModal";
import { useToast, ToastContainer } from "@/components/ui/Toast";
import StatusBadge from "@/components/StatusBadge";
import PostingProgress from "@/components/PostingProgress";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import type { MarketplacePost } from "@/types";

export default function PostsPage() {
  const [posts, setPosts] = useState<MarketplacePost[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isBulkUploadOpen, setIsBulkUploadOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingPost, setEditingPost] = useState<MarketplacePost | null>(null);
  const [selectedPosts, setSelectedPosts] = useState<number[]>([]); // For pending posts
  const [selectedPostedItems, setSelectedPostedItems] = useState<number[]>([]); // For posted items
  const [activeJobId, setActiveJobId] = useState<string | null>(null); // NEW: Track active posting job

  // Confirmation dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    type: "danger" | "warning" | "success" | "info";
    onConfirm: () => void;
    confirmText?: string;
  }>({
    isOpen: false,
    title: "",
    message: "",
    type: "warning",
    onConfirm: () => {},
  });

  const [activityLogs, setActivityLogs] = useState<
    Array<{
      id: number;
      type: "create" | "edit" | "delete" | "post" | "bulk" | "account";
      message: string;
      details: string;
      timestamp: Date;
    }>
  >([]);
  const { toasts, removeToast, success, error: showError } = useToast();

  // Counter to ensure unique IDs for activity logs
  const logIdCounterRef = useRef(0);

  // Load activity logs from localStorage on mount
  useEffect(() => {
    const savedLogs = localStorage.getItem("activityLogs");
    if (savedLogs) {
      try {
        const parsedLogs = JSON.parse(savedLogs) as Array<{
          id: number;
          type: "create" | "edit" | "delete" | "post" | "bulk" | "account";
          message: string;
          details: string;
          timestamp: string;
        }>;

        // Convert timestamp strings back to Date objects and regenerate unique IDs
        const logsWithDates = parsedLogs.map((log) => {
          // Generate new unique ID to avoid duplicates from localStorage
          logIdCounterRef.current += 1;
          const uniqueId = Date.now() * 1000 + logIdCounterRef.current;

          return {
            ...log,
            id: uniqueId, // Replace with new unique ID
            timestamp: new Date(log.timestamp),
          };
        });

        // Filter out logs older than 24 hours
        const now = new Date();
        const twentyFourHoursAgo = new Date(
          now.getTime() - 24 * 60 * 60 * 1000
        );
        const recentLogs = logsWithDates.filter(
          (log) => log.timestamp.getTime() > twentyFourHoursAgo.getTime()
        );

        setActivityLogs(recentLogs);
      } catch (error) {
        console.error("Failed to load activity logs:", error);
        // Clear corrupted localStorage data
        localStorage.removeItem("activityLogs");
      }
    }
  }, []);

  // Save activity logs to localStorage whenever they change
  useEffect(() => {
    if (activityLogs.length > 0) {
      localStorage.setItem("activityLogs", JSON.stringify(activityLogs));
    }
  }, [activityLogs]);

  useEffect(() => {
    fetchPosts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cleanup old logs every minute
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      const now = new Date();
      const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

      setActivityLogs((prev) =>
        prev.filter(
          (log) => log.timestamp.getTime() > twentyFourHoursAgo.getTime()
        )
      );
    }, 60000); // Run every 60 seconds

    return () => clearInterval(cleanupInterval);
  }, []);

  // Helper function to add activity log
  const addActivityLog = (
    type: "create" | "edit" | "delete" | "post" | "bulk" | "account",
    message: string,
    details: string
  ) => {
    const now = new Date();
    const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    // Generate unique ID using timestamp + counter
    logIdCounterRef.current += 1;
    const uniqueId = Date.now() * 1000 + logIdCounterRef.current;

    const newLog = {
      id: uniqueId,
      type,
      message,
      details,
      timestamp: new Date(),
    };

    // Filter out logs older than 24 hours and add new log
    setActivityLogs((prev) => {
      const recentLogs = prev.filter(
        (log) => log.timestamp.getTime() > twentyFourHoursAgo.getTime()
      );
      return [newLog, ...recentLogs];
    });
  };

  const fetchPosts = async () => {
    try {
      setLoading(true);
      const response = await postsAPI.list();
      setPosts(response.data);
    } catch (err) {
      showError("Failed to load posts");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    const postToDelete = posts.find((p) => p.id === id);

    setConfirmDialog({
      isOpen: true,
      title: "Delete Post",
      message: `Are you sure you want to delete "${
        postToDelete?.title || "this post"
      }"? This action cannot be undone.`,
      type: "danger",
      confirmText: "Delete",
      onConfirm: async () => {
        try {
          await postsAPI.delete(id);
          setPosts(posts.filter((post) => post.id !== id));
          setSelectedPosts(selectedPosts.filter((postId) => postId !== id));
          setSelectedPostedItems(
            selectedPostedItems.filter((postId) => postId !== id)
          );
          success("Post deleted successfully");

          // Log the deletion
          if (postToDelete) {
            addActivityLog(
              "delete",
              "Post deleted",
              `"${postToDelete.title}" removed from listings`
            );
          }
        } catch (err) {
          showError("Failed to delete post");
          console.error(err);
        }
      },
    });
  };

  const handleEdit = (post: MarketplacePost) => {
    setEditingPost(post);
    setIsEditModalOpen(true);
  };

  const handleSelectPost = (postId: number) => {
    if (selectedPosts.includes(postId)) {
      setSelectedPosts(selectedPosts.filter((id) => id !== postId));
    } else {
      setSelectedPosts([...selectedPosts, postId]);
    }
  };

  const handleSelectAll = () => {
    const pendingPosts = posts.filter((p) => !p.posted);
    if (selectedPosts.length === pendingPosts.length) {
      // Deselect all
      setSelectedPosts([]);
    } else {
      // Select all pending posts
      setSelectedPosts(pendingPosts.map((post) => post.id));
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedPosts.length === 0) {
      showError("Please select at least one post to delete");
      return;
    }

    const count = selectedPosts.length;

    setConfirmDialog({
      isOpen: true,
      title: "Delete Selected Posts",
      message: `Are you sure you want to delete ${count} selected post(s)? This action cannot be undone.`,
      type: "danger",
      confirmText: "Delete All",
      onConfirm: async () => {
        try {
          await Promise.all(selectedPosts.map((id) => postsAPI.delete(id)));
          setPosts(posts.filter((post) => !selectedPosts.includes(post.id)));
          success(`Successfully deleted ${count} post(s)`);

          // Log bulk deletion
          addActivityLog(
            "delete",
            "Bulk deletion",
            `${count} pending posts removed from queue`
          );
          setSelectedPosts([]);
        } catch (err) {
          showError("Failed to delete selected posts");
          console.error(err);
        }
      },
    });
  };

  const handleStartPosting = async () => {
    // If no posts are selected, use all pending posts
    const pendingPosts = posts.filter((p) => !p.posted);
    const postsToPost =
      selectedPosts.length > 0 ? selectedPosts : pendingPosts.map((p) => p.id);

    if (postsToPost.length === 0) {
      showError("No pending posts available");
      return;
    }

    const count = postsToPost.length;

    // Get the posts that will be posted to extract account info
    const postsToPostData = posts.filter((p) => postsToPost.includes(p.id));

    // Extract unique accounts
    const uniqueAccounts = new Set(
      postsToPostData
        .map((p) => (typeof p.account === "object" ? p.account.email : ""))
        .filter((email) => email !== "")
    );
    const accountsList = Array.from(uniqueAccounts);

    const message =
      selectedPosts.length > 0
        ? `Start posting ${count} selected post(s) to Facebook Marketplace?`
        : `Start posting all ${count} pending post(s) to Facebook Marketplace?`;

    setConfirmDialog({
      isOpen: true,
      title: "Start Posting",
      message: message,
      type: "info",
      confirmText: "Start Posting",
      onConfirm: async () => {
        try {
          // Log the start of posting with account details
          const accountsText =
            accountsList.length === 1
              ? `account: ${accountsList[0]}`
              : `${accountsList.length} accounts: ${accountsList.join(", ")}`;

          addActivityLog(
            "post",
            "Posting initiated",
            `Starting to post ${count} item(s) using ${accountsText}`
          );

          const response = await postsAPI.startPosting(postsToPost);
          success(response.data.message || `Started posting ${count} post(s)!`);

          // NEW: Get job_id from response and show real-time progress
          if (response.data.job_id) {
            setActiveJobId(response.data.job_id);
          }

          setSelectedPosts([]);
        } catch (err) {
          const error = err as { response?: { data?: { error?: string } } };
          const errorMsg =
            error.response?.data?.error || "Failed to start posting process";
          showError(errorMsg);

          // Log the failure
          addActivityLog(
            "post",
            "Posting failed",
            `Failed to start posting: ${errorMsg}`
          );

          console.error(err);
        }
      },
    });
  };

  // Functions for Posted Items
  const handleSelectPostedItem = (postId: number) => {
    if (selectedPostedItems.includes(postId)) {
      setSelectedPostedItems(selectedPostedItems.filter((id) => id !== postId));
    } else {
      setSelectedPostedItems([...selectedPostedItems, postId]);
    }
  };

  const handleSelectAllPosted = () => {
    const postedPosts = posts.filter((p) => p.posted);
    if (selectedPostedItems.length === postedPosts.length) {
      // Deselect all
      setSelectedPostedItems([]);
    } else {
      // Select all posted items
      setSelectedPostedItems(postedPosts.map((post) => post.id));
    }
  };

  const handleDeleteSelectedPosted = async () => {
    // If no items are selected, use all posted items
    const postedPosts = posts.filter((p) => p.posted);
    const itemsToDelete =
      selectedPostedItems.length > 0
        ? selectedPostedItems
        : postedPosts.map((p) => p.id);

    if (itemsToDelete.length === 0) {
      showError("No posted items available to delete");
      return;
    }

    const count = itemsToDelete.length;
    const message =
      selectedPostedItems.length > 0
        ? `Are you sure you want to delete ${count} selected posted item(s)?`
        : `Are you sure you want to delete all ${count} posted item(s)?`;

    setConfirmDialog({
      isOpen: true,
      title: "Delete Posted Items",
      message: message + " This action cannot be undone.",
      type: "danger",
      confirmText: "Delete",
      onConfirm: async () => {
        try {
          await Promise.all(itemsToDelete.map((id) => postsAPI.delete(id)));
          setPosts(posts.filter((post) => !itemsToDelete.includes(post.id)));
          success(`Successfully deleted ${count} posted item(s)`);

          // Log deletion of posted items
          addActivityLog(
            "delete",
            "Posted items deleted",
            `${count} posted item(s) removed from listings`
          );

          setSelectedPostedItems([]);
        } catch (err) {
          showError("Failed to delete some posted items");
          console.error(err);
        }
      },
    });
  };

  const stats = {
    total: posts.length,
    posted: posts.filter((p) => p.posted).length,
    pending: posts.filter((p) => !p.posted).length,
    failed: posts.filter((p) => p.status === "failed").length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading posts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog({ ...confirmDialog, isOpen: false })}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        message={confirmDialog.message}
        type={confirmDialog.type}
        confirmText={confirmDialog.confirmText}
      />

      {/* Real-Time Posting Progress - NEW */}
      {activeJobId && (
        <PostingProgress
          jobId={activeJobId}
          onComplete={() => {
            setActiveJobId(null);
            fetchPosts(); // Refresh posts when job completes
            addActivityLog(
              "post",
              "Posting completed",
              "All posts have been processed"
            );
          }}
        />
      )}

      {/* Create Post Modal */}
      <CreatePostModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={() => {
          fetchPosts();
          addActivityLog(
            "create",
            "Post created",
            "New post added to pending posts"
          );
        }}
        onToast={(type, message) => {
          if (type === "success") success(message);
          else showError(message);
        }}
      />

      {/* Edit Post Modal */}
      <EditPostModal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setEditingPost(null);
        }}
        onSuccess={() => {
          fetchPosts();
          if (editingPost) {
            addActivityLog(
              "edit",
              "Post updated",
              `"${editingPost.title}" has been edited`
            );
          }
        }}
        onToast={(type, message) => {
          if (type === "success") success(message);
          else showError(message);
        }}
        post={editingPost}
      />

      {/* Bulk Upload Modal */}
      <BulkUploadPostsModal
        isOpen={isBulkUploadOpen}
        onClose={() => setIsBulkUploadOpen(false)}
        onSuccess={(count?: number) => {
          fetchPosts();
          addActivityLog(
            "bulk",
            "Bulk upload completed",
            count
              ? `${count} posts uploaded successfully`
              : "Multiple posts uploaded successfully"
          );
        }}
        onToast={(type, message) => {
          if (type === "success") success(message);
          else showError(message);
        }}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Marketplace Posts
          </h1>
          <p className="text-gray-700 mt-1">
            Manage your Facebook Marketplace listings
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            onClick={() => setIsBulkUploadOpen(true)}
            variant="purple"
            className="flex items-center gap-2"
          >
            <Package size={20} />
            Create Multiple Posts
          </Button>
          <Button
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2"
          >
            <Plus size={20} />
            Create Single Post
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">
              Total Posts
            </CardTitle>
            <Package className="h-4 w-4 text-gray-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">
              {stats.total}
            </div>
            <p className="text-xs text-gray-600">All marketplace listings</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">
              Posted
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.posted}
            </div>
            <p className="text-xs text-gray-600">Successfully posted</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">
              Pending
            </CardTitle>
            <XCircle className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {stats.pending}
            </div>
            <p className="text-xs text-gray-600">Awaiting posting</p>
          </CardContent>
        </Card>
      </div>

      {/* Two Boxes: Pending Posts (Left) and Posted (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Posts Box - LEFT SIDE */}
        <Card className="flex flex-col h-[650px]">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-gray-900">
                <XCircle className="h-5 w-5 text-orange-600" />
                Pending Posts ({stats.pending})
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col overflow-hidden">
            <div className="space-y-3 flex-1 overflow-y-auto">
              {posts.filter((p) => !p.posted).length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <XCircle className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                  <p>No pending posts</p>
                </div>
              ) : (
                posts
                  .filter((p) => !p.posted)
                  .map((post) => (
                    <div
                      key={post.id}
                      className={`border rounded-lg p-3 transition-colors ${
                        selectedPosts.includes(post.id)
                          ? "bg-blue-50 border-blue-300"
                          : "hover:bg-gray-50"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Checkbox */}
                        <input
                          type="checkbox"
                          checked={selectedPosts.includes(post.id)}
                          onChange={() => handleSelectPost(post.id)}
                          className="mt-1 h-5 w-5 text-blue-600 rounded border-gray-300 focus:ring-2 focus:ring-blue-500 cursor-pointer flex-shrink-0"
                          aria-label={`Select post: ${post.title}`}
                        />
                        <div className="relative w-16 h-16 flex-shrink-0 bg-gray-200 rounded overflow-hidden">
                          {post.image ? (
                            <Image
                              src={post.image}
                              alt={post.title}
                              fill
                              className="object-cover"
                              sizes="64px"
                            />
                          ) : (
                            <div className="flex items-center justify-center h-full">
                              <ImageIcon className="h-6 w-6 text-gray-400" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="font-semibold text-sm text-gray-900 truncate">
                              {post.title}
                            </h4>
                            <StatusBadge posted={post.posted} />
                          </div>
                          <p className="text-xs text-gray-600 line-clamp-1">
                            {post.description}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-sm font-bold text-blue-600">
                              ${post.price}
                            </span>
                            <span className="text-xs text-gray-400">•</span>
                            <span className="text-xs text-gray-600">
                              {new Date(
                                post.scheduled_time
                              ).toLocaleDateString()}
                            </span>
                          </div>
                          <div className="text-xs text-gray-700 mt-1 truncate">
                            <span className="font-medium">Account:</span>{" "}
                            {post.account.email}
                          </div>
                          {post.retry_count > 0 && (
                            <div className="text-xs text-orange-600 mt-1">
                              Retries: {post.retry_count}
                            </div>
                          )}
                          <div className="flex gap-1 mt-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleEdit(post)}
                              className="text-xs px-2 py-1 h-auto"
                            >
                              <Edit size={12} className="mr-1" />
                              Edit
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => handleDelete(post.id)}
                              className="text-xs px-2 py-1 h-auto"
                            >
                              <Trash2 size={12} className="mr-1" />
                              Delete
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
              )}
            </div>

            {/* Action Buttons - Below Pending Posts - Fixed to Bottom */}
            <div className="flex gap-2 mt-4 pt-4 border-t flex-shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSelectAll}
                className="flex-1"
                disabled={posts.filter((p) => !p.posted).length === 0}
              >
                {selectedPosts.length === posts.filter((p) => !p.posted).length
                  ? "Deselect All"
                  : "Select All"}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteSelected}
                disabled={selectedPosts.length === 0}
                className="flex-1"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Selected
              </Button>
              <Button
                onClick={handleStartPosting}
                className="bg-green-600 hover:bg-green-700 text-white flex-1"
                size="sm"
                disabled={posts.filter((p) => !p.posted).length === 0}
              >
                <CheckCircle className="h-4 w-4 mr-2" />
                Start Posting
                {selectedPosts.length > 0 && ` (${selectedPosts.length})`}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Posted Box - RIGHT SIDE */}
        <Card className="flex flex-col h-[650px]">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-gray-900">
                <CheckCircle className="h-5 w-5 text-green-600" />
                Posted ({stats.posted})
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col overflow-hidden">
            <div className="space-y-3 flex-1 overflow-y-auto">
              {posts.filter((p) => p.posted).length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <CheckCircle className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                  <p>No posted items yet</p>
                </div>
              ) : (
                posts
                  .filter((p) => p.posted)
                  .map((post) => (
                    <div
                      key={post.id}
                      className={`border rounded-lg p-3 transition-colors ${
                        selectedPostedItems.includes(post.id)
                          ? "bg-green-50 border-green-300"
                          : "hover:bg-gray-50"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Checkbox */}
                        <input
                          type="checkbox"
                          checked={selectedPostedItems.includes(post.id)}
                          onChange={() => handleSelectPostedItem(post.id)}
                          className="mt-1 h-5 w-5 text-green-600 rounded border-gray-300 focus:ring-2 focus:ring-green-500 cursor-pointer flex-shrink-0"
                          aria-label={`Select posted item: ${post.title}`}
                        />
                        <div className="relative w-16 h-16 flex-shrink-0 bg-gray-200 rounded overflow-hidden">
                          {post.image ? (
                            <Image
                              src={post.image}
                              alt={post.title}
                              fill
                              className="object-cover"
                              sizes="64px"
                            />
                          ) : (
                            <div className="flex items-center justify-center h-full">
                              <ImageIcon className="h-6 w-6 text-gray-400" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="font-semibold text-sm text-gray-900 truncate">
                              {post.title}
                            </h4>
                            <StatusBadge posted={post.posted} />
                          </div>
                          <p className="text-xs text-gray-600 line-clamp-1">
                            {post.description}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-sm font-bold text-blue-600">
                              ${post.price}
                            </span>
                            <span className="text-xs text-gray-400">•</span>
                            <span className="text-xs text-gray-600">
                              {new Date(
                                post.scheduled_time
                              ).toLocaleDateString()}
                            </span>
                          </div>
                          <div className="text-xs text-gray-700 mt-1 truncate">
                            <span className="font-medium">Account:</span>{" "}
                            {post.account.email}
                          </div>
                          <div className="flex gap-1 mt-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleEdit(post)}
                              className="text-xs px-2 py-1 h-auto"
                            >
                              <Edit size={12} className="mr-1" />
                              Edit
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => handleDelete(post.id)}
                              className="text-xs px-2 py-1 h-auto"
                            >
                              <Trash2 size={12} className="mr-1" />
                              Delete
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
              )}
            </div>

            {/* Action Buttons - Below Posted Items - Fixed to Bottom */}
            <div className="flex gap-2 mt-4 pt-4 border-t flex-shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSelectAllPosted}
                className="flex-1"
                disabled={posts.filter((p) => p.posted).length === 0}
              >
                {selectedPostedItems.length ===
                posts.filter((p) => p.posted).length
                  ? "Deselect All"
                  : "Select All"}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteSelectedPosted}
                className="flex-1"
                disabled={posts.filter((p) => p.posted).length === 0}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
                {selectedPostedItems.length > 0 &&
                  ` (${selectedPostedItems.length})`}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Logs Section - BELOW THE TWO BOXES */}
      <Card>
        <CardHeader>
          <CardTitle>Activity Logs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {activityLogs.length === 0 ? (
              <div className="text-sm text-gray-500 text-center py-4">
                No activity yet. Create, edit, or post items to see logs here.
              </div>
            ) : (
              activityLogs.map((log) => {
                // Determine border color based on log type
                const borderColor =
                  {
                    create: "border-blue-500",
                    edit: "border-yellow-500",
                    delete: "border-red-500",
                    post: "border-green-500",
                    bulk: "border-orange-500",
                    account: "border-purple-500",
                  }[log.type] || "border-gray-500";

                // Format timestamp
                const timeAgo = (() => {
                  const now = new Date();
                  const diff = now.getTime() - log.timestamp.getTime();
                  const minutes = Math.floor(diff / 60000);
                  const hours = Math.floor(diff / 3600000);
                  const days = Math.floor(diff / 86400000);

                  if (minutes < 1) return "Just now";
                  if (minutes < 60)
                    return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
                  if (hours < 24)
                    return `${hours} hour${hours > 1 ? "s" : ""} ago`;
                  return `${days} day${days > 1 ? "s" : ""} ago`;
                })();

                return (
                  <div
                    key={log.id}
                    className={`text-sm text-gray-600 border-l-4 ${borderColor} pl-3 py-2`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{log.message}</span>
                      <span className="text-xs text-gray-400">{timeAgo}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{log.details}</p>
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
