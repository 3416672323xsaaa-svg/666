package org.bilipink;

import android.content.Context;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import android.os.Build;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;

public final class MediaMerger {

    private MediaMerger() {
    }

    /**
     * 将独立的视频文件和音频文件封装成一个 MP4 文件。
     *
     * 不使用 FFmpeg，不重新编码。
     *
     * @return 合并成功返回 true，否则返回 false。
     */
    public static boolean merge(
            Context context,
            String videoPath,
            String audioPath,
            String outputPath
    ) {
        if (context == null
                || videoPath == null
                || audioPath == null
                || outputPath == null) {
            return false;
        }

        File videoFile = new File(videoPath);
        File audioFile = new File(audioPath);
        File outputFile = new File(outputPath);

        if (!videoFile.isFile()
                || !audioFile.isFile()
                || videoFile.length() <= 0
                || audioFile.length() <= 0) {
            return false;
        }

        File parent = outputFile.getParentFile();

        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            return false;
        }

        if (outputFile.exists() && !outputFile.delete()) {
            return false;
        }

        MediaExtractor videoExtractor = new MediaExtractor();
        MediaExtractor audioExtractor = new MediaExtractor();
        MediaMuxer muxer = null;

        boolean muxerStarted = false;
        boolean success = false;

        try {
            videoExtractor.setDataSource(videoPath);
            audioExtractor.setDataSource(audioPath);

            int videoTrack = findTrack(videoExtractor, "video/");
            int audioTrack = findTrack(audioExtractor, "audio/");

            if (videoTrack < 0 || audioTrack < 0) {
                throw new IOException(
                        "无法识别视频或音频轨道，输入格式可能不受支持。"
                );
            }

            MediaFormat videoFormat =
                    videoExtractor.getTrackFormat(videoTrack);

            MediaFormat audioFormat =
                    audioExtractor.getTrackFormat(audioTrack);

            videoExtractor.selectTrack(videoTrack);
            audioExtractor.selectTrack(audioTrack);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                muxer = new MediaMuxer(
                        outputPath,
                        MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4
                );
            } else {
                muxer = new MediaMuxer(
                        outputPath,
                        MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4
                );
            }

            int outputVideoTrack = muxer.addTrack(videoFormat);
            int outputAudioTrack = muxer.addTrack(audioFormat);

            muxer.start();
            muxerStarted = true;

            copySamples(
                    videoExtractor,
                    muxer,
                    outputVideoTrack
            );

            copySamples(
                    audioExtractor,
                    muxer,
                    outputAudioTrack
            );

            muxer.stop();
            muxerStarted = false;

            success = outputFile.isFile()
                    && outputFile.length() > 0;

        } catch (Exception e) {
            android.util.Log.e(
                    "BiliPink",
                    "音视频合并失败：" + e.getMessage(),
                    e
            );
            success = false;

        } finally {
            if (muxer != null) {
                if (muxerStarted) {
                    try {
                        muxer.stop();
                    } catch (Exception ignored) {
                    }
                }

                try {
                    muxer.release();
                } catch (Exception ignored) {
                }
            }

            try {
                videoExtractor.release();
            } catch (Exception ignored) {
            }

            try {
                audioExtractor.release();
            } catch (Exception ignored) {
            }

            if (!success && outputFile.exists()) {
                // 合并失败时删除不完整的输出文件。
                //noinspection ResultOfMethodCallIgnored
                outputFile.delete();
            }
        }

        return success;
    }

    private static int findTrack(
            MediaExtractor extractor,
            String mimePrefix
    ) {
        int trackCount = extractor.getTrackCount();

        for (int i = 0; i < trackCount; i++) {
            MediaFormat format = extractor.getTrackFormat(i);

            if (!format.containsKey(MediaFormat.KEY_MIME)) {
                continue;
            }

            String mime = format.getString(MediaFormat.KEY_MIME);

            if (mime != null && mime.startsWith(mimePrefix)) {
                return i;
            }
        }

        return -1;
    }

    private static void copySamples(
            MediaExtractor extractor,
            MediaMuxer muxer,
            int outputTrack
    ) throws IOException {

        final int bufferSize = 2 * 1024 * 1024;
        ByteBuffer buffer = ByteBuffer.allocate(bufferSize);

        MediaMuxer.BufferInfo info = new MediaMuxer.BufferInfo();

        while (true) {
            buffer.clear();

            int sampleSize = extractor.readSampleData(buffer, 0);

            if (sampleSize < 0) {
                break;
            }

            if (sampleSize > buffer.capacity()) {
                throw new IOException("媒体数据块超过缓冲区容量。");
            }

            info.offset = 0;
            info.size = sampleSize;
            info.presentationTimeUs =
                    extractor.getSampleTime();

            int flags = extractor.getSampleFlags();

            info.flags = 0;

            if ((flags & MediaExtractor.SAMPLE_FLAG_SYNC) != 0) {
                info.flags |= MediaMuxer
                        .BUFFER_FLAG_KEY_FRAME;
            }

            muxer.writeSampleData(
                    outputTrack,
                    buffer,
                    info
            );

            if (!extractor.advance()) {
                break;
            }
        }
    }
              }
