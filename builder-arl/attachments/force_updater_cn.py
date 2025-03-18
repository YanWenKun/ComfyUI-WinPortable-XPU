import os
import re
import sys
import git
from concurrent.futures import ThreadPoolExecutor
from gooey import Gooey, GooeyParser

@Gooey(
    program_name="ComfyUI 强制更新工具",  # 程序名称
    language='chinese',
    progress_regex=r"^进度: (\d+)%$",  # 进度条正则表达式
    progress_expr="进度: {0}%",  # 进度条显示格式
    timing_options={
        'show_time_remaining': False,  # 不显示剩余时间
        'show_elapsed_time': True,  # 显示已过时间
    },
    disable_progress_bar_animation=True,  # 禁用进度条动画
    clear_before_run=True,  # 运行前清空控制台
)
def main():
    # 创建 Gooey 参数解析器
    parser = GooeyParser(
        description="强制更新 ComfyUI 及其自定义节点，且将远程 GitHub 地址替换为国内镜像。\n\n"
                    "提示：强制更新仅处理 Git 仓库， 不处理 Python 依赖包，\n"
                    "后续可能需要在 Manager 中点击 Try Fix 修复个别节点。"
    )

    # 设置默认目录
    default_comfyui_dir = os.path.join(os.getcwd(), 'ComfyUI')
    default_custom_nodes_dir = os.path.join(os.getcwd(), 'ComfyUI', 'custom_nodes')

    parser.add_argument(
        'comfyui_dir',  # 参数名称
        metavar='ComfyUI 目录',  # 参数显示名称
        help='选择 ComfyUI 根目录',  # 帮助信息
        widget='DirChooser',  # 使用目录选择器
        default=default_comfyui_dir,  # 设置默认值
    )
    parser.add_argument(
        'custom_nodes_dir',  # 参数名称
        metavar='自定义节点目录',  # 参数显示名称
        help='选择 custom_nodes 目录',  # 帮助信息
        widget='DirChooser',  # 使用目录选择器
        default=default_custom_nodes_dir,  # 设置默认值
    )
    args = parser.parse_args()

    # 获取 custom_nodes 目录下的文件夹总数
    custom_nodes = [D for D in os.listdir(args.custom_nodes_dir) if os.path.isdir(os.path.join(args.custom_nodes_dir, D))]
    total_tasks = len(custom_nodes) + 1  # 包括 ComfyUI 根目录
    completed_tasks = 0

    # 更新进度条
    def update_progress():
        nonlocal completed_tasks
        completed_tasks += 1
        progress = int((completed_tasks / total_tasks) * 100)
        print(f"进度: {progress}%")  # Gooey 会根据正则表达式更新进度条
        sys.stdout.flush()  # 强制刷新输出，确保 Gooey 捕获到进度信息

    # 更新主仓库
    try:
        set_url_and_pull(args.comfyui_dir)
        update_progress()
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)  # 终止程序

    # 更新 custom_nodes 目录下的所有子目录
    with ThreadPoolExecutor() as executor:
        futures = []
        for D in custom_nodes:
            dir_path = os.path.join(args.custom_nodes_dir, D)
            futures.append(executor.submit(set_url_and_pull, dir_path))

        # 等待所有任务完成
        for future in futures:
            try:
                future.result()  # 获取任务结果，如果任务中有异常会抛出
                update_progress()
            except Exception as e:
                print(f"错误: {e}")
                sys.exit(1)  # 终止程序

def set_url_and_pull(repo_path):
    try:
        repo = git.Repo(repo_path)
        git_remote_url = repo.remotes.origin.url

        # 判断是否是国内镜像地址
        if git_remote_url.startswith(('https://gh-proxy.com/', 'https://ghfast.top/')):
            print(f"正在更新: {repo_path}")
            repo.git.reset('--hard')
            repo.remotes.origin.pull()
            print(f"更新完成: {repo_path}")
        # 判断是否是 GitHub 地址
        elif git_remote_url.startswith('https://github.com/'):
            print(f"正在修改URL并更新: {repo_path}")
            repo.git.reset('--hard')
            # 将 GitHub 地址替换为国内镜像地址
            new_url = git_remote_url.replace('https://github.com/', 'https://ghfast.top/https://github.com/')
            repo.remotes.origin.set_url(new_url)
            repo.remotes.origin.pull()
            print(f"更新完成: {repo_path}")
        # 判断是否是 ghp.ci 代理地址
        elif git_remote_url.startswith('https://ghp.ci/'):
            print(f"正在修改URL并更新: {repo_path}")
            repo.git.reset('--hard')
            # 更新已失效镜像地址
            new_url = git_remote_url.replace('https://ghp.ci/', 'https://ghfast.top/')
            repo.remotes.origin.set_url(new_url)
            repo.remotes.origin.pull()
            print(f"更新完成: {repo_path}")
        else:
            print(f"忽略未知 URL 格式的仓库: {repo_path}")
    except Exception as e:
        print(f"处理 {repo_path} 时出错: {e}")
        raise  # 重新抛出异常，让上层捕获并终止程序

if __name__ == "__main__":
    main()
